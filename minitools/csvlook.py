"""csvlook - preview a CSV as an aligned text table or a Markdown table.

Columns are padded to their widest cell; all-numeric columns are right-aligned
so digits line up. `-n` limits the preview to the first N data rows (0 = all)
and `--max-width` cuts long cells with an ellipsis. `--markdown` prints a
GitHub-style table (pipes in cells escaped) ready to paste into a README or
issue. Wide characters (CJK, most emoji) count as two columns. Reads a file
or stdin ("-"); a "showing N of M rows" note goes to stderr. `-c a,b`
shows only those columns, in that order (unknown names list the real ones).

    python -m minitools.csvlook sales.csv -n 10
    python -m minitools.csvlook sales.csv -c country,amount
    python -m minitools.csvlook sales.csv --markdown --max-width 30 -d ';'
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
from pathlib import Path

NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?%?$")
ELLIPSIS = "…"


def display_width(text: str) -> int:
    """Terminal columns used by ``text``: wide/full-width characters count double."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def truncate(text: str, max_width: int | None) -> str:
    """Cut ``text`` to at most ``max_width`` display columns, ending with an ellipsis."""
    if max_width is None or display_width(text) <= max_width:
        return text
    if max_width < 1:
        raise ValueError("max_width must be >= 1")
    out, used = "", 0
    for ch in text:
        w = display_width(ch)
        if used + w > max_width - 1:
            break
        out, used = out + ch, used + w
    return out + ELLIPSIS


def numeric_columns(rows: list[list[str]], ncols: int) -> list[bool]:
    """True for columns whose non-empty cells are all numbers (and that have at least one)."""
    flags = []
    for i in range(ncols):
        cells = [r[i].strip() for r in rows if i < len(r) and r[i].strip()]
        flags.append(bool(cells) and all(NUMBER.match(c) for c in cells))
    return flags


def _pad(text: str, width: int, right: bool) -> str:
    gap = " " * (width - display_width(text))
    return gap + text if right else text + gap


def select_columns(header: list[str], rows: list[list[str]], names: list[str]) -> tuple[list[str], list[list[str]]]:
    """Keep only the columns called ``names`` (trimmed, in that order); short rows give empty cells.

    Raises KeyError naming the unknown columns and listing the real headers.
    """
    stripped = [h.strip() for h in header]
    wanted = [n.strip() for n in names if n.strip()]
    if not wanted:
        raise KeyError("no column names given")
    unknown = [n for n in wanted if n not in stripped]
    if unknown:
        raise KeyError(f"unknown column(s): {', '.join(unknown)} (available: {', '.join(stripped)})")
    idx = [stripped.index(n) for n in wanted]
    return [header[i] for i in idx], [[r[i] if i < len(r) else "" for i in idx] for r in rows]


def render(header: list[str], rows: list[list[str]], markdown: bool = False, max_width: int | None = None) -> str:
    """Format header + rows as an aligned table; short rows are padded with empty cells."""
    ncols = max([len(header)] + [len(r) for r in rows])
    header = header + [""] * (ncols - len(header))
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    right = numeric_columns(rows, ncols)

    def clean(cell: str) -> str:
        cell = " ".join(cell.split())  # newlines/tabs inside quoted cells would break the layout
        cell = truncate(cell, max_width)
        return cell.replace("|", "\\|") if markdown else cell

    table = [[clean(c) for c in header]] + [[clean(c) for c in r] for r in rows]
    widths = [max(display_width(row[i]) for row in table) for i in range(ncols)]
    if markdown:
        widths = [max(w, 3) for w in widths]  # "---" is the shortest separator
        lines = ["| " + " | ".join(_pad(c, w, False) for c, w in zip(table[0], widths)) + " |"]
        seps = [("-" * (w - 1) + ":") if r else "-" * w for w, r in zip(widths, right)]
        lines.append("| " + " | ".join(seps) + " |")
        for row in table[1:]:
            lines.append("| " + " | ".join(_pad(c, w, r) for c, w, r in zip(row, widths, right)) + " |")
    else:
        lines = ["  ".join(_pad(c, w, False) for c, w in zip(table[0], widths)).rstrip()]
        lines.append("  ".join("-" * w for w in widths))
        for row in table[1:]:
            lines.append("  ".join(_pad(c, w, r) for c, w, r in zip(row, widths, right)).rstrip())
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-n", "--rows", type=int, default=20, help="data rows to show (default 20, 0 = all)")
    p.add_argument("--max-width", type=int, help="cut cells longer than this many columns")
    p.add_argument("--markdown", action="store_true", help="print a Markdown table")
    p.add_argument("-c", "--columns", help="comma-separated column names to show, in this order")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    args = p.parse_args(argv)

    if args.rows < 0:
        print("csvlook: --rows must be 0 or more", file=sys.stderr)
        return 2
    if args.max_width is not None and args.max_width < 1:
        print("csvlook: --max-width must be at least 1", file=sys.stderr)
        return 2
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvlook: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvlook: input has no header row", file=sys.stderr)
        return 1
    header, data = rows[0], rows[1:]
    if args.columns:
        try:
            header, data = select_columns(header, data, args.columns.split(","))
        except KeyError as e:
            print(f"csvlook: {e.args[0]}", file=sys.stderr)
            return 2
    shown = data if args.rows == 0 else data[: args.rows]
    sys.stdout.write(render(header, shown, markdown=args.markdown, max_width=args.max_width))
    if len(shown) < len(data):
        print(f"csvlook: showing {len(shown)} of {len(data)} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

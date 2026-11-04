"""csvsplitcol - split one CSV column into several new columns.

Exports often pack two or three values into one cell: "Breda, NL", a full name,
"2026-11-04 13:05", "SKU-123/blue". `-c location --sep "," --into city,country`
replaces the `location` column with `city` and `country` at the same position.
Parts are trimmed. The split happens at most N-1 times for N new columns, so the
last new column keeps the rest of the cell ("Den Haag, Zuid-Holland, NL" with
`--into city,rest` gives "Den Haag" and "Zuid-Holland, NL"); `--from-right`
splits from the right instead, so a last name or extension stays whole on the
right side. Cells with fewer parts leave the remaining new columns empty.

Without `--sep` the cell is split on runs of whitespace. `--keep` keeps the
original column and puts the new ones right after it.

    python -m minitools.csvsplitcol people.csv -c location --sep "," --into city,country
    python -m minitools.csvsplitcol people.csv -c name --into first,last --from-right --keep
    python -m minitools.csvsplitcol log.csv -c ts --into date,time -d ';' --stats

Reads a file or stdin ("-"), writes stdout or -o. Unknown columns list the real
headers; new names that clash with existing headers or repeat are rejected
(exit 2).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


class ColumnError(ValueError):
    pass


def _raw_parts(cell: str, n: int, sep: str | None, from_right: bool) -> list[str]:
    text = cell.strip()
    if not text:
        return []
    parts = text.rsplit(sep, n - 1) if from_right else text.split(sep, n - 1)
    return [p.strip() for p in parts]


def split_cell(cell: str, n: int, sep: str | None = None, from_right: bool = False) -> list[str]:
    """Split ``cell`` into exactly ``n`` trimmed parts, padding with "" when it has fewer."""
    parts = _raw_parts(cell, n, sep, from_right)
    pad = [""] * (n - len(parts))
    return pad + parts if from_right else parts + pad


def plan_header(header: list[str], column: str, into: list[str], keep: bool) -> tuple[int, list[str]]:
    """Return (index of the split column, new header); raise ColumnError on bad names."""
    if column not in header:
        raise ColumnError(f"unknown column: {column}; available: {', '.join(header)}")
    if not into or any(not n for n in into):
        raise ColumnError("--into needs one or more non-empty column names")
    repeated = sorted({n for n in into if into.count(n) > 1})
    if repeated:
        raise ColumnError(f"--into repeats: {', '.join(repeated)}")
    idx = header.index(column)
    remaining = header if keep else header[:idx] + header[idx + 1:]
    clash = [n for n in into if n in remaining]
    if clash:
        raise ColumnError(f"new column(s) already exist: {', '.join(clash)}")
    new_header = header[: idx + 1] + into + header[idx + 1:] if keep else header[:idx] + into + header[idx + 1:]
    return idx, new_header


def split_rows(
    rows: list[list[str]], idx: int, n: int, sep: str | None = None, from_right: bool = False, keep: bool = False
) -> tuple[list[list[str]], int]:
    """Split column ``idx`` of every row; returns (new rows, rows that had fewer than n parts)."""
    out: list[list[str]] = []
    short = 0
    for row in rows:
        row = row + [""] * (idx + 1 - len(row)) if len(row) <= idx else row
        cell = row[idx]
        parts = split_cell(cell, n, sep, from_right)
        if cell.strip() and len(_raw_parts(cell, n, sep, from_right)) < n:
            short += 1
        head = row[: idx + 1] if keep else row[:idx]
        out.append(head + parts + row[idx + 1:])
    return out, short


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--column", required=True, help="column to split")
    p.add_argument("--into", required=True, help="comma-separated names of the new columns")
    p.add_argument("--sep", help="separator text (default: runs of whitespace)")
    p.add_argument("--from-right", action="store_true", help="split from the right; the first new column keeps the rest")
    p.add_argument("--keep", action="store_true", help="keep the original column before the new ones")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    p.add_argument("--stats", action="store_true", help="report rows that had fewer parts than new columns on stderr")
    args = p.parse_args(argv)

    if args.sep == "":
        print("csvsplitcol: --sep cannot be empty", file=sys.stderr)
        return 2
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvsplitcol: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvsplitcol: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    into = [n.strip() for n in args.into.split(",")]
    try:
        idx, new_header = plan_header(header, args.column.strip(), into, args.keep)
    except ColumnError as e:
        print(f"csvsplitcol: {e}", file=sys.stderr)
        return 2

    body, short = split_rows(rows[1:], idx, len(into), args.sep, args.from_right, args.keep)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(new_header)
    writer.writerows(body)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    if args.stats:
        print(f"csvsplitcol: split {len(body)} rows, {short} with fewer than {len(into)} parts", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

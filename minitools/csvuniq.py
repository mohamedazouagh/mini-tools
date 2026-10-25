"""csvuniq - keep one CSV row per key, dropping repeats of the same id.

`dedupe` and `csvclean --dedupe` only drop rows that are identical. Exports
often repeat a record with some cells changed (a customer exported twice with
a newer order count), so the duplicate is defined by key columns, not by the
whole row. `-k customer_id` (or `-k email,country`) keeps the first row of
each key; `--keep last` keeps the final one instead, at the position of that
last row, which is what you want when later rows are newer. Key cells are
trimmed; `-i` also ignores case. `--dupes` does the opposite and writes only
the rows whose key occurs more than once (all copies, in file order), to see
what would be dropped. `--count copies` appends a column with how many input
rows shared each output row's key, so you can see which records were merged.

    python -m minitools.csvuniq customers.csv -k customer_id --keep last -o unique.csv
    python -m minitools.csvuniq contacts.csv -k email -i --stats
    python -m minitools.csvuniq orders.csv -k order_id --dupes -d ';'

Reads a file or stdin ("-"), writes stdout or -o. Unknown column names list the
real headers (exit 2).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path


class ColumnError(ValueError):
    pass


def resolve_columns(header: list[str], names: list[str]) -> list[int]:
    missing = [n for n in names if n not in header]
    if missing:
        raise ColumnError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    if not names:
        raise ColumnError("no key columns given")
    return [header.index(n) for n in names]


def row_key(row: list[str], idx: list[int], ignore_case: bool = False) -> tuple[str, ...]:
    cells = [(row[i] if i < len(row) else "").strip() for i in idx]
    return tuple(c.casefold() for c in cells) if ignore_case else tuple(cells)


def unique_rows(
    rows: list[list[str]], idx: list[int], keep: str = "first", ignore_case: bool = False
) -> list[list[str]]:
    """One row per key. ``keep`` is "first" or "last"; output stays in file order."""
    if keep not in ("first", "last"):
        raise ValueError(f"keep must be 'first' or 'last', got {keep!r}")
    keys = [row_key(r, idx, ignore_case) for r in rows]
    chosen: dict[tuple[str, ...], int] = {}
    for pos, k in enumerate(keys):
        if keep == "last" or k not in chosen:
            chosen[k] = pos
    keep_pos = set(chosen.values())
    return [r for pos, r in enumerate(rows) if pos in keep_pos]


def duplicate_rows(rows: list[list[str]], idx: list[int], ignore_case: bool = False) -> list[list[str]]:
    """All rows whose key appears more than once, in file order."""
    keys = [row_key(r, idx, ignore_case) for r in rows]
    counts = Counter(keys)
    return [r for r, k in zip(rows, keys) if counts[k] > 1]


def add_count_column(
    out: list[list[str]], body: list[list[str]], idx: list[int], width: int, ignore_case: bool = False
) -> list[list[str]]:
    """Append how many input rows share each output row's key (short rows padded to ``width``)."""
    counts = Counter(row_key(r, idx, ignore_case) for r in body)
    return [r + [""] * (width - len(r)) + [str(counts[row_key(r, idx, ignore_case)])] for r in out]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-k", "--key", required=True, help="comma-separated key column(s)")
    p.add_argument("--keep", choices=["first", "last"], default="first", help="which row of a key survives")
    p.add_argument("-i", "--ignore-case", action="store_true", help="compare keys case-insensitively")
    p.add_argument("--dupes", action="store_true", help="write only rows whose key is repeated")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    p.add_argument("--stats", action="store_true", help="print row counts to stderr")
    p.add_argument("--count", metavar="NAME", help="add a column NAME with how many rows share the key")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvuniq: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvuniq: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        idx = resolve_columns(header, [n.strip() for n in args.key.split(",") if n.strip()])
        if args.count is not None and (not args.count.strip() or args.count.strip() in header):
            raise ColumnError(f"--count needs a new, non-empty column name, got {args.count!r}")
    except ColumnError as e:
        print(f"csvuniq: {e}", file=sys.stderr)
        return 2

    body = rows[1:]
    if args.dupes:
        out = duplicate_rows(body, idx, args.ignore_case)
    else:
        out = unique_rows(body, idx, args.keep, args.ignore_case)
    n_out = len(out)
    out_header = header
    if args.count is not None:
        out = add_count_column(out, body, idx, len(header), args.ignore_case)
        out_header = header + [args.count.strip()]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(out_header)
    writer.writerows(out)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    if args.stats:
        n_keys = len({row_key(r, idx, args.ignore_case) for r in body})
        label = "repeated rows" if args.dupes else "rows kept"
        print(f"csvuniq: {len(body)} rows, {n_keys} distinct keys, {n_out} {label}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

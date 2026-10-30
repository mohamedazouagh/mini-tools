"""csvsort - sort CSV rows by one or more columns, numbers as numbers.

A key column whose non-empty cells all parse as numbers is sorted
numerically (so 10 comes after 9); any other column is sorted as text,
case-insensitively. A key written as `amount:desc` (or `:asc`) sets the
direction for that column only, e.g. country A-Z but amount high to low;
`--reverse` flips every key. Empty cells always go last, in both directions.
The sort is stable, so rows with equal keys keep their input order.
Unknown column names fail with the list of real headers. Quoted cells that
span several lines (notes, addresses) keep their line breaks.

    python -m minitools.csvsort in.csv -k country,amount:desc [-r] [-d ';'] [-o out.csv]
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


def _number(cell: str) -> float | None:
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if value == value and abs(value) != float("inf") else None


def parse_key(spec: str, header: list[str]) -> tuple[str, bool]:
    """Split "amount:desc" into ("amount", True); "name" or "name:asc" sort ascending.

    A header that itself contains ":desc" / ":asc" wins over the suffix, so such
    columns stay reachable.
    """
    name, sep, direction = spec.rpartition(":")
    if sep and direction.lower() in ("asc", "desc") and spec not in header:
        return name, direction.lower() == "desc"
    return spec, False


def sort_rows(header: list[str], rows: list[list[str]], keys: list[str], reverse: bool = False) -> list[list[str]]:
    """Sort by ``keys`` (most significant first); ``"col:desc"`` flips one key, ``reverse`` flips all."""
    parsed = [parse_key(k, header) for k in keys]
    missing = [name for name, _ in parsed if name not in header]
    if missing:
        raise KeyError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    rows = [r + [""] * (len(header) - len(r)) for r in rows]
    # sort by the least significant key first; stability keeps earlier keys' order
    for key, desc in reversed(parsed):
        i = header.index(key)
        descending = desc != reverse
        cells = [r[i].strip() for r in rows]
        numeric = all(_number(c) is not None for c in cells if c)
        filled = [r for r, c in zip(rows, cells) if c]
        empty = [r for r, c in zip(rows, cells) if not c]
        if numeric:
            filled.sort(key=lambda r: float(r[i]), reverse=descending)
        else:
            filled.sort(key=lambda r: r[i].strip().casefold(), reverse=descending)
        rows = filled + empty
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-k", "--keys", required=True, help="comma-separated column names, most significant first; add :desc to sort one key descending")
    p.add_argument("-r", "--reverse", action="store_true", help="sort descending (empty cells stay last)")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ,)")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)
    if len(args.delimiter) != 1:
        p.error("--delimiter must be a single character")
    keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    if not keys:
        p.error("--keys needs at least one column name")

    if args.input == "-":
        text = sys.stdin.read()
    else:
        src = Path(args.input)
        if not src.is_file():
            print(f"csvsort: no such file: {src}", file=sys.stderr)
            return 1
        text = src.read_text(encoding="utf-8-sig")
    # parse the text as one stream, not line by line: splitting into lines first
    # silently drops the line breaks inside quoted multi-line cells
    table = [r for r in csv.reader(io.StringIO(text, newline=""), delimiter=args.delimiter) if r]
    if not table:
        print("csvsort: input is empty", file=sys.stderr)
        return 1
    header, rows = table[0], table[1:]
    try:
        rows = sort_rows(header, rows, keys, args.reverse)
    except KeyError as exc:
        print(f"csvsort: {exc.args[0]}", file=sys.stderr)
        return 1

    out = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.writer(out, delimiter=args.delimiter, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""csv2json - convert a CSV file to a JSON array of objects (or JSON Lines).

The reverse of json2csv. Every row becomes an object keyed by the header.
By default all values stay strings, exactly as in the file; `--types` turns
integers, decimals and true/false into JSON numbers and booleans and empty
cells into null. `--nest` rebuilds nested objects from dotted headers
(`address.city` -> {"address": {"city": ...}}), matching what json2csv
flattens. Reads a file or stdin ("-"), writes stdout or -o.

    python -m minitools.csv2json in.csv [-o out.json] [-d ';'] [--types] [--nest]
    python -m minitools.csv2json in.csv --lines -o out.jsonl
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

_INT = re.compile(r"-?(0|[1-9]\d*)")
_FLOAT = re.compile(r"-?(0|[1-9]\d*)\.\d+")


class HeaderError(ValueError):
    pass


def convert_value(cell: str) -> object:
    """Typed value for a cell: int, float, bool, None for empty, else the string.

    Deliberately conservative: leading zeros ("007", a postcode or ID), "1e5",
    "nan" and thousands separators stay strings, so nothing is silently
    reinterpreted.
    """
    text = cell.strip()
    if text == "":
        return None
    if _INT.fullmatch(text):
        return int(text)
    if _FLOAT.fullmatch(text):
        return float(text)
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return cell


def check_header(header: list[str]) -> None:
    """Reject blank or duplicate column names: both would lose data in an object."""
    blanks = [str(i + 1) for i, h in enumerate(header) if not h]
    if blanks:
        raise HeaderError(f"blank column name at position(s): {', '.join(blanks)}")
    dupes = sorted({h for h in header if header.count(h) > 1})
    if dupes:
        raise HeaderError(f"duplicate column name(s): {', '.join(dupes)}")


def nest(record: dict[str, object]) -> dict[str, object]:
    """Turn dotted keys into nested objects; a key that is both a value and a parent is an error."""
    out: dict[str, object] = {}
    for key, value in record.items():
        parts = key.split(".")
        node = out
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise HeaderError(f"column {key!r} conflicts with column {part!r}")
            node = child
        if parts[-1] in node:
            raise HeaderError(f"column {key!r} conflicts with a nested column")
        node[parts[-1]] = value
    return out


def rows_to_records(rows: list[list[str]], types: bool = False, nested: bool = False) -> list[dict]:
    """Records from CSV rows (first row is the header); short rows padded, extra cells rejected."""
    header = [h.strip() for h in rows[0]]
    check_header(header)
    records = []
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) > len(header):
            raise HeaderError(f"row {line_no} has {len(row)} cells but the header has {len(header)}")
        cells = row + [""] * (len(header) - len(row))
        rec = {h: (convert_value(c) if types else c) for h, c in zip(header, cells)}
        records.append(nest(rec) if nested else rec)
    return records


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    p.add_argument("--types", action="store_true", help="numbers/booleans as JSON types, empty cells as null")
    p.add_argument("--nest", action="store_true", help="rebuild nested objects from dotted headers (a.b)")
    p.add_argument("--lines", action="store_true", help="write JSON Lines (one object per line)")
    p.add_argument("--indent", type=int, default=2, help="indent for array output (default 2, 0 = compact)")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csv2json: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csv2json: input has no header row", file=sys.stderr)
        return 1
    try:
        records = rows_to_records(rows, types=args.types, nested=args.nest)
    except HeaderError as e:
        print(f"csv2json: {e}", file=sys.stderr)
        return 2

    if args.lines:
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    else:
        text = json.dumps(records, ensure_ascii=False, indent=args.indent or None) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

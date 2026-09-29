"""json2csv - convert a JSON array of objects to CSV.

Columns are the union of all keys (in first-seen order). Nested objects are
flattened with dots ({"a": {"b": 1}} -> column "a.b"); lists are written as
JSON text. Missing keys become empty cells.

    python -m minitools.json2csv input.json output.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def flatten(obj: dict, prefix: str = "") -> dict:
    flat: dict = {}
    for key, value in obj.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}."))
        elif isinstance(value, list):
            flat[name] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flat[name] = ""
        else:
            flat[name] = value
    return flat


def to_table(records: list) -> tuple[list[str], list[dict]]:
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError("expected a JSON array of objects")
    rows = [flatten(r) for r in records]
    columns: dict[str, None] = {}
    for row in rows:
        columns.update(dict.fromkeys(row))
    return list(columns), rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args(argv)
    try:
        records = json.loads(args.input.read_text(encoding="utf-8-sig"))
        columns, rows = to_table(records)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"json2csv: {exc}", file=sys.stderr)
        return 1
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} records, {len(columns)} columns -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

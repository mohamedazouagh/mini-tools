"""json2csv - convert a JSON array of objects to CSV.

Columns are the union of all keys (in first-seen order). Nested objects are
flattened with dots ({"a": {"b": 1}} -> column "a.b"); lists are written as
JSON text. Missing keys become empty cells.

JSON Lines input (one object per line) is read with --lines, or automatically
when the input file ends in .jsonl / .ndjson. Blank lines are skipped.

When the array is wrapped in an object (typical API responses), point at it
with --path, e.g. --path data.items; list indexes work too (pages.0.rows).

    python -m minitools.json2csv input.json output.csv
    python -m minitools.json2csv events.jsonl output.csv
    python -m minitools.json2csv response.json output.csv --path data.items
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


def parse_json_lines(text: str) -> list:
    """Parse JSON Lines; errors name the offending line number."""
    records = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: {exc.msg}") from exc
    return records


def select_path(data, path: str):
    """Walk a dotted path like "data.items" into nested objects.

    API responses often wrap the records ({"data": {"items": [...]}}). Numeric
    parts index into lists ("pages.0.rows"). Errors name the part that failed.
    """
    current = data
    walked = []
    for part in path.split("."):
        walked.append(part)
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ValueError(f"--path: nothing at {'.'.join(walked)!r}")
    return current


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--lines", action="store_true", help="input is JSON Lines (auto for .jsonl/.ndjson)")
    p.add_argument("--path", help='dotted path to the array inside a wrapper object, e.g. "data.items"')
    args = p.parse_args(argv)
    lines_mode = args.lines or args.input.suffix.lower() in (".jsonl", ".ndjson")
    if lines_mode and args.path:
        print("json2csv: --path cannot be combined with JSON Lines input", file=sys.stderr)
        return 1
    try:
        text = args.input.read_text(encoding="utf-8-sig")
        records = parse_json_lines(text) if lines_mode else json.loads(text)
        if args.path:
            records = select_path(records, args.path)
        elif isinstance(records, dict):
            arrays = [k for k, v in records.items() if isinstance(v, list)]
            hint = f" (try --path {arrays[0]})" if arrays else ""
            raise ValueError(f"expected a JSON array of objects, got an object{hint}")
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

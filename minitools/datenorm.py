"""datenorm - rewrite the dates in one CSV column as ISO 8601 (YYYY-MM-DD).

Understands ISO dates, day-first numeric dates (28-09-2026, 28/09/2026,
28.09.2026), compact 20260928 and month names (28 Sep 2026, Sep 28, 2026,
28 September 2026). Numeric dates are read day-first unless --monthfirst is
given. Cells that cannot be parsed are left unchanged and reported; with
--strict the tool exits with an error instead of writing output.

    python -m minitools.datenorm input.csv output.csv --column date [--monthfirst] [--strict]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

_NUMERIC = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$")
_ISO_LIKE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_TEXT_FORMATS = ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y")


def parse_date(text: str, monthfirst: bool = False) -> date | None:
    """Return the date in `text`, or None if it is empty or not recognised."""
    t = " ".join(text.strip().split())
    if not t:
        return None
    try:
        if m := _ISO_LIKE.match(t):
            y, mo, d = map(int, m.groups())
            return date(y, mo, d)
        if m := _NUMERIC.match(t):
            a, b, y = map(int, m.groups())
            mo, d = (a, b) if monthfirst else (b, a)
            return date(y, mo, d)
        if len(t) == 8 and t.isdigit():
            return date(int(t[:4]), int(t[4:6]), int(t[6:]))
    except ValueError:
        return None
    for fmt in _TEXT_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def normalise_rows(rows: list[dict], column: str, monthfirst: bool = False) -> list[int]:
    """Rewrite rows[i][column] in place; return the 1-based data row numbers that failed."""
    failed = []
    for i, row in enumerate(rows, start=1):
        value = row.get(column) or ""
        parsed = parse_date(value, monthfirst)
        if parsed is not None:
            row[column] = parsed.isoformat()
        elif value.strip():
            failed.append(i)
    return failed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--column", "-c", required=True, help="name of the date column")
    p.add_argument("--monthfirst", action="store_true", help="read 09/28/2026 style dates (US order)")
    p.add_argument("--strict", action="store_true", help="fail if any non-empty cell cannot be parsed")
    args = p.parse_args(argv)
    with args.input.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    if args.column not in fields:
        print(f"datenorm: column {args.column!r} not found (have: {', '.join(fields)})", file=sys.stderr)
        return 1
    failed = normalise_rows(rows, args.column, args.monthfirst)
    if failed and args.strict:
        print(f"datenorm: could not parse rows {failed[:10]}", file=sys.stderr)
        return 1
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    note = f", {len(failed)} left unchanged (rows {failed[:10]})" if failed else ""
    print(f"{len(rows) - len(failed)} of {len(rows)} dates normalised{note} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

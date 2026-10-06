"""csvstats - quick per-column profile of a CSV file.

For every column: how many cells are filled or empty, how many distinct
values there are, and - when every filled cell is a number - min, max and
mean. NaN/inf spellings and underscores count as text. Numbers may use a decimal comma ("3,5") when --decimal-comma is given.
Handy as a first look before cleaning or loading a file.

    python -m minitools.csvstats data.csv [-d ';'] [--decimal-comma] [--csv]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from statistics import mean


def _number(cell: str, decimal_comma: bool) -> float | None:
    """Parse a cell as a finite number, or return None.

    float() also accepts "nan", "inf" and "1_000", which in a CSV are text
    (a name like "Nan", a typo) rather than numbers, so those are rejected.
    """
    text = cell.strip()
    if "_" in text:
        return None
    if decimal_comma:
        text = text.replace(".", "").replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def profile(rows: Iterable[dict[str, str]], columns: list[str], decimal_comma: bool = False) -> list[dict]:
    """One summary dict per column, in header order.

    Cells that are empty or whitespace-only count as empty. A column is
    numeric only if it has at least one filled cell and all filled cells
    parse as numbers; otherwise min/max/mean are None.
    """
    filled: dict[str, list[str]] = {c: [] for c in columns}
    total = 0
    for row in rows:
        total += 1
        for c in columns:
            cell = (row.get(c) or "").strip()
            if cell:
                filled[c].append(cell)
    out = []
    for c in columns:
        cells = filled[c]
        nums = [_number(x, decimal_comma) for x in cells]
        numeric = bool(cells) and all(n is not None for n in nums)
        out.append(
            {
                "column": c,
                "filled": len(cells),
                "empty": total - len(cells),
                "distinct": len(set(cells)),
                "min": min(nums) if numeric else None,
                "max": max(nums) if numeric else None,
                "mean": round(mean(nums), 4) if numeric else None,
            }
        )
    return out


FIELDS = ["column", "filled", "empty", "distinct", "min", "max", "mean"]


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path, help="CSV file with a header row")
    p.add_argument("-d", "--delimiter", default=",", help="field separator (default ',')")
    p.add_argument("--decimal-comma", action="store_true", help="read '1.234,5' style numbers")
    p.add_argument("--csv", action="store_true", help="print the profile as CSV instead of a table")
    args = p.parse_args(argv)

    if not args.input.is_file():
        print(f"csvstats: no such file: {args.input}", file=sys.stderr)
        return 1
    with args.input.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        if not reader.fieldnames:
            print(f"csvstats: {args.input} has no header row", file=sys.stderr)
            return 1
        stats = profile(reader, list(reader.fieldnames), args.decimal_comma)

    if args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows({k: ("" if v is None else v) for k, v in s.items()} for s in stats)
        return 0
    table = [FIELDS] + [[_fmt(s[k]) for k in FIELDS] for s in stats]
    widths = [max(len(r[i]) for r in table) for i in range(len(FIELDS))]
    for r in table:
        print("  ".join(cell.ljust(w) if i == 0 else cell.rjust(w) for i, (cell, w) in enumerate(zip(r, widths))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

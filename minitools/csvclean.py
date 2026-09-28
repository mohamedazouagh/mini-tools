"""csvclean — tidy a messy CSV.

Trims whitespace in every cell, normalises header names to snake_case,
drops fully empty rows and (optionally) exact duplicate rows.

    python -m minitools.csvclean input.csv output.csv [--dedupe]
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def snake(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip())
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.strip("_").lower()


def clean_rows(rows: list[list[str]], dedupe: bool = False) -> list[list[str]]:
    if not rows:
        return []
    header = [snake(h) for h in rows[0]]
    out, seen = [header], set()
    for row in rows[1:]:
        cells = [c.strip() for c in row]
        if not any(cells):
            continue
        key = tuple(cells)
        if dedupe and key in seen:
            continue
        seen.add(key)
        out.append(cells)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--dedupe", action="store_true", help="drop exact duplicate rows")
    args = p.parse_args(argv)
    with args.input.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    cleaned = clean_rows(rows, dedupe=args.dedupe)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(cleaned)
    print(f"{len(rows) - 1} rows in, {len(cleaned) - 1} rows out -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

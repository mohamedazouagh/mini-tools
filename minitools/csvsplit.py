"""csvsplit - split a CSV into smaller files, repeating the header in each.

Two modes:
  --rows N     chunks of at most N data rows: in_001.csv, in_002.csv, ...
  --by COLUMN  one file per distinct value of COLUMN: in_<value>.csv
Values are made filename-safe; an empty value goes to in_empty.csv. Existing
files are never overwritten unless --force is given.

    python -m minitools.csvsplit data.csv --rows 1000 [-o outdir] [-d ';']
    python -m minitools.csvsplit data.csv --by country [-o outdir] [--force]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path


def chunk_rows(rows: Iterable[list[str]], size: int) -> Iterator[list[list[str]]]:
    """Yield lists of at most ``size`` rows, in order."""
    if size < 1:
        raise ValueError("size must be >= 1")
    batch: list[list[str]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def safe_name(value: str) -> str:
    """Filename-safe version of a cell value: unsafe characters become '_'."""
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip()).strip("._")
    return cleaned or "empty"


def group_rows(rows: Iterable[list[str]], index: int) -> dict[str, list[list[str]]]:
    """Group rows by the safe name of column ``index``, keeping first-seen order.

    Different raw values that map to the same safe name (e.g. "a/b" and
    "a b") share one group. Short rows count as an empty value.
    """
    groups: dict[str, list[list[str]]] = {}
    for row in rows:
        key = safe_name(row[index] if index < len(row) else "")
        groups.setdefault(key, []).append(row)
    return groups


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path, help="CSV file with a header row")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--rows", type=int, metavar="N", help="max data rows per output file")
    mode.add_argument("--by", metavar="COLUMN", help="one output file per value of this column")
    p.add_argument("-o", "--outdir", type=Path, help="output folder (default: next to the input)")
    p.add_argument("-d", "--delimiter", default=",", help="field separator (default ',')")
    p.add_argument("--force", action="store_true", help="overwrite existing output files")
    args = p.parse_args(argv)

    if args.rows is not None and args.rows < 1:
        p.error("--rows must be at least 1")
    if not args.input.is_file():
        print(f"csvsplit: no such file: {args.input}", file=sys.stderr)
        return 1
    with args.input.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=args.delimiter)
        header = next(reader, None)
        if not header:
            print(f"csvsplit: {args.input} has no header row", file=sys.stderr)
            return 1
        rows = [r for r in reader if any(cell.strip() for cell in r)]

    stem, outdir = args.input.stem, args.outdir or args.input.parent
    if args.rows is not None:
        chunks = list(chunk_rows(rows, args.rows))
        width = max(3, len(str(len(chunks))))
        plan = {outdir / f"{stem}_{i:0{width}d}.csv": c for i, c in enumerate(chunks, start=1)}
    else:
        if args.by not in header:
            print(f"csvsplit: no column {args.by!r}; columns are: {', '.join(header)}", file=sys.stderr)
            return 1
        groups = group_rows(rows, header.index(args.by))
        plan = {outdir / f"{stem}_{key}.csv": g for key, g in groups.items()}

    clashes = [path for path in plan if path.exists()]
    if clashes and not args.force:
        print(f"csvsplit: {len(clashes)} output file(s) already exist, e.g. {clashes[0]}; use --force", file=sys.stderr)
        return 1
    outdir.mkdir(parents=True, exist_ok=True)
    for path, chunk in plan.items():
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=args.delimiter, lineterminator="\n")
            w.writerow(header)
            w.writerows(chunk)
        print(f"{path.name}: {len(chunk)} rows")
    print(f"{len(rows)} rows -> {len(plan)} files in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

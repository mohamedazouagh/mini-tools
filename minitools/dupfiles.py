"""dupfiles - find files with identical content in a folder tree (read-only).

Files are first grouped by size (cheap), and only sizes shared by two or more
files are hashed with SHA-256, read in chunks so large files do not fill
memory. Each group of identical files is printed with its size; nothing is
ever deleted or moved. Empty files are skipped unless --include-empty.

Exit code: 0 no duplicates, 1 duplicates found, 2 bad input.

    python -m minitools.dupfiles photos
    python -m minitools.dupfiles downloads --min-size 1M --glob "*.pdf" --csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

CHUNK = 1 << 20
UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}


def parse_size(text: str) -> int:
    """'500', '64K', '1.5M', '2G' -> bytes (binary units, case-insensitive)."""
    t = text.strip().upper().removesuffix("B")
    unit = t[-1] if t and t[-1] in "KMG" else ""
    number = t[: -1] if unit else t
    try:
        value = float(number)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a size: {text!r} (use e.g. 500, 64K, 1.5M)") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"size must be >= 0: {text!r}")
    return int(value * UNITS[unit])


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(
    files: list[Path], min_size: int = 0, include_empty: bool = False
) -> list[tuple[int, list[Path]]]:
    """Groups of identical files as (size, sorted paths), largest size first."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    for f in files:
        size = f.stat().st_size
        if size < min_size or (size == 0 and not include_empty):
            continue
        by_size[size].append(f)
    groups = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for f in candidates:
            by_hash[file_hash(f)].append(f)
        groups += [(size, sorted(paths)) for paths in by_hash.values() if len(paths) > 1]
    return sorted(groups, key=lambda g: (-g[0], g[1]))


def human(n: int) -> str:
    for unit in ("B", "K", "M"):
        if n < 1024:
            return f"{n}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}G"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", type=Path)
    p.add_argument("--glob", default="*", help="only consider files matching this glob (default: all)")
    p.add_argument("--no-recursive", action="store_true", help="only look directly inside FOLDER")
    p.add_argument("--min-size", type=parse_size, default=0, help="ignore files smaller than this (e.g. 64K, 1M)")
    p.add_argument("--include-empty", action="store_true", help="also report empty files as duplicates")
    p.add_argument("--csv", action="store_true", help="print group,size,path rows instead of text")
    args = p.parse_args(argv)

    if not args.folder.is_dir():
        print(f"dupfiles: no such folder: {args.folder}", file=sys.stderr)
        return 2
    walker = args.folder.glob if args.no_recursive else args.folder.rglob
    files = [f for f in walker(args.glob) if f.is_file() and not f.is_symlink()]
    groups = find_duplicates(files, args.min_size, args.include_empty)

    if args.csv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["group", "size", "path"])
        for i, (size, paths) in enumerate(groups, 1):
            for path in paths:
                w.writerow([i, size, path.relative_to(args.folder).as_posix()])
    else:
        for size, paths in groups:
            print(f"{len(paths)} x {human(size)}")
            for path in paths:
                print(f"  {path.relative_to(args.folder).as_posix()}")
    wasted = sum(size * (len(paths) - 1) for size, paths in groups)
    print(
        f"dupfiles: {len(files)} file(s) scanned, {len(groups)} duplicate group(s), {human(wasted)} reclaimable",
        file=sys.stderr,
    )
    return 1 if groups else 0


if __name__ == "__main__":
    raise SystemExit(main())

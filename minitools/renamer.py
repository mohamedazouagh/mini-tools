"""renamer - bulk-rename files in one folder with a regex, dry run by default.

The regex is applied to each file name (not the folder path) with re.sub, so
groups work in the replacement ("\\1"). Only files directly inside FOLDER are
considered; --glob narrows them further. Without --apply nothing is touched:
the planned renames are printed so you can check them first.

The whole plan is validated before anything moves: if two files would get the
same name, a new name already belongs to another file, or a new name is empty
or contains a path separator, nothing is renamed and the exit code is 1.

    python -m minitools.renamer photos "^IMG_(\\d+)" "holiday_\\1"          # preview
    python -m minitools.renamer photos "^IMG_(\\d+)" "holiday_\\1" --apply  # do it
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def plan_renames(names: list[str], pattern: str, replacement: str, ignore_case: bool = False) -> list[tuple[str, str]]:
    """Return (old, new) pairs for names the regex actually changes, sorted by old name."""
    regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    plan = []
    for name in sorted(names):
        new = regex.sub(replacement, name)
        if new != name:
            plan.append((name, new))
    return plan


def find_conflicts(plan: list[tuple[str, str]], existing: list[str]) -> list[str]:
    """Human-readable problems that make the plan unsafe; empty list means OK."""
    problems = []
    targets: dict[str, str] = {}
    sources = {old for old, _ in plan}
    for old, new in plan:
        if not new or new in (".", "..") or "/" in new or "\\" in new:
            problems.append(f"{old!r} -> {new!r}: not a valid file name")
            continue
        key = new.casefold()  # Windows and macOS folders are case-insensitive
        if key in targets:
            problems.append(f"{old!r} and {targets[key]!r} would both become {new!r}")
        targets[key] = old
    for old, new in plan:
        for name in existing:
            same_file = name == old
            if name.casefold() == new.casefold() and not same_file and name not in sources:
                problems.append(f"{old!r} -> {new!r}: {name!r} already exists")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", type=Path)
    p.add_argument("pattern", help="regular expression matched against each file name")
    p.add_argument("replacement", help=r"replacement text; \1, \2 ... insert groups")
    p.add_argument("--glob", default="*", help="only consider files matching this glob (default: all)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="case-insensitive regex")
    p.add_argument("--apply", action="store_true", help="actually rename (default is a dry run)")
    args = p.parse_args(argv)

    if not args.folder.is_dir():
        print(f"renamer: no such folder: {args.folder}", file=sys.stderr)
        return 1
    try:
        files = [f.name for f in args.folder.glob(args.glob) if f.is_file()]
        plan = plan_renames(files, args.pattern, args.replacement, args.ignore_case)
    except re.error as exc:
        print(f"renamer: bad pattern or replacement: {exc}", file=sys.stderr)
        return 1

    existing = [f.name for f in args.folder.iterdir()]
    problems = find_conflicts(plan, existing)
    for old, new in plan:
        print(f"{old} -> {new}")
    if problems:
        for msg in problems:
            print(f"renamer: {msg}", file=sys.stderr)
        print("renamer: nothing renamed", file=sys.stderr)
        return 1
    if not plan:
        print("renamer: no file names match", file=sys.stderr)
        return 0
    if not args.apply:
        print(f"dry run: {len(plan)} file(s) would be renamed; add --apply to do it", file=sys.stderr)
        return 0
    _apply(args.folder, plan)
    print(f"renamed {len(plan)} file(s)", file=sys.stderr)
    return 0


def _apply(folder: Path, plan: list[tuple[str, str]]) -> None:
    # Two phases via temporary names so swaps and chains (a->b, b->c) cannot clobber each other.
    temps = []
    for i, (old, new) in enumerate(plan):
        tmp = folder / f".renamer-tmp-{i}-{old}"
        (folder / old).rename(tmp)
        temps.append((tmp, new))
    for tmp, new in temps:
        tmp.rename(folder / new)


if __name__ == "__main__":
    raise SystemExit(main())

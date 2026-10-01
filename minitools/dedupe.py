"""dedupe - remove duplicate lines from a text file, keeping the first occurrence.

Order is preserved (unlike `sort -u`). Optionally compare lines ignoring case
and/or surrounding whitespace, skip blank lines, and print a summary of how
many duplicates were dropped. Reads a file or stdin ("-"), writes stdout or
--output.

    python -m minitools.dedupe input.txt [-o out.txt] [--ignore-case] [--strip] [--skip-blank] [--stats]
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path


def dedupe_lines(
    lines: Iterable[str],
    ignore_case: bool = False,
    strip: bool = False,
    skip_blank: bool = False,
) -> Iterator[str]:
    """Yield each line the first time its comparison key is seen.

    The line is yielded as it was read (only the trailing newline is
    normalised by the caller); `ignore_case` and `strip` only affect the key.
    """
    seen: set[str] = set()
    for line in lines:
        key = line.strip() if strip else line
        if skip_blank and not key.strip():
            continue
        if ignore_case:
            key = key.casefold()
        if key in seen:
            continue
        seen.add(key)
        yield line


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='text file, or "-" for stdin')
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    p.add_argument("-i", "--ignore-case", action="store_true", help="treat 'Breda' and 'breda' as duplicates")
    p.add_argument("-s", "--strip", action="store_true", help="ignore leading/trailing whitespace when comparing")
    p.add_argument("--skip-blank", action="store_true", help="drop empty / whitespace-only lines")
    p.add_argument("--stats", action="store_true", help="print kept/dropped counts to stderr")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"dedupe: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")
    lines = raw.splitlines()
    kept = list(dedupe_lines(lines, args.ignore_case, args.strip, args.skip_blank))
    text = "".join(f"{line}\n" for line in kept)

    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.stats:
        print(f"dedupe: kept {len(kept)} of {len(lines)} lines, dropped {len(lines) - len(kept)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

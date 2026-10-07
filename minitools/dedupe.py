"""dedupe - remove duplicate lines from a text file, keeping the first occurrence.

Order is preserved (unlike `sort -u`). Optionally compare lines ignoring case
and/or surrounding whitespace, skip blank lines, and print a summary of how
many duplicates were dropped. `--keep-last` keeps the last occurrence of
each line instead of the first. `--only-dupes` flips the tool into an audit
mode: print only the lines that occur more than once (like `uniq -d`, but
without sorting), with `--stats` reporting how often each repeats. Reads a file or stdin ("-"), writes stdout
or --output.

    python -m minitools.dedupe input.txt [-o out.txt] [--ignore-case] [--strip] [--skip-blank] [--keep-last] [--only-dupes] [--stats]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path


def _key_func(ignore_case: bool, strip: bool, skip_blank: bool):
    def key_of(line: str) -> str | None:
        key = line.strip() if strip else line
        if skip_blank and not key.strip():
            return None
        return key.casefold() if ignore_case else key

    return key_of


def duplicate_lines(
    lines: Iterable[str],
    ignore_case: bool = False,
    strip: bool = False,
    skip_blank: bool = False,
) -> list[tuple[str, int]]:
    """Lines whose comparison key occurs more than once, as (first occurrence, count).

    Returned in order of first appearance; each duplicated key is listed once.
    """
    key_of = _key_func(ignore_case, strip, skip_blank)
    counts: Counter[str] = Counter()
    first: dict[str, str] = {}
    for line in lines:
        key = key_of(line)
        if key is None:
            continue
        counts[key] += 1
        first.setdefault(key, line)
    return [(first[k], n) for k, n in counts.items() if n > 1]


def dedupe_lines(
    lines: Iterable[str],
    ignore_case: bool = False,
    strip: bool = False,
    skip_blank: bool = False,
    keep_last: bool = False,
) -> Iterator[str]:
    """Yield each line the first time its comparison key is seen.

    The line is yielded as it was read (only the trailing newline is
    normalised by the caller); `ignore_case` and `strip` only affect the key.
    With `keep_last`, the last occurrence of each key is kept instead, at its
    own position (useful when later lines are corrections of earlier ones).
    """

    key_of = _key_func(ignore_case, strip, skip_blank)

    if keep_last:
        buffered = list(lines)
        last_index = {}
        for i, line in enumerate(buffered):
            key = key_of(line)
            if key is not None:
                last_index[key] = i
        keep = set(last_index.values())
        yield from (line for i, line in enumerate(buffered) if i in keep)
        return

    seen: set[str] = set()
    for line in lines:
        key = key_of(line)
        if key is None or key in seen:
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
    p.add_argument("--keep-last", action="store_true", help="keep the last occurrence of each line instead of the first")
    p.add_argument(
        "--only-dupes", action="store_true", help="print only lines that occur more than once (first occurrence each)"
    )
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
    if args.only_dupes:
        if args.keep_last:
            print("dedupe: --only-dupes cannot be combined with --keep-last", file=sys.stderr)
            return 2
        dupes = duplicate_lines(lines, args.ignore_case, args.strip, args.skip_blank)
        text = "".join(f"{line}\n" for line, _ in dupes)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        if args.stats:
            print(f"dedupe: {len(dupes)} line(s) repeated", file=sys.stderr)
            for line, n in dupes:
                print(f"  {n}x {line}", file=sys.stderr)
        return 0
    kept = list(dedupe_lines(lines, args.ignore_case, args.strip, args.skip_blank, args.keep_last))
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

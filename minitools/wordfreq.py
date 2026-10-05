"""wordfreq - count lines, words and characters, and list the most frequent words.

Words are runs of letters, digits, apostrophes or hyphens inside a word
(Unicode-aware, so "café" and "e-mail" count as one word). Counting is
case-insensitive. `--min-length` ignores short words and `--stopwords FILE`
ignores words listed one per line. Reads files or stdin ("-"). Files are
read as UTF-8 by default; `--encoding cp1252` (or latin-1, ...) handles
older exports, and an undecodable file gives a clear error, not a traceback.

    python -m minitools.wordfreq notes.txt [more.txt ...] [-n 10] [--min-length 3] [--stopwords stop.txt] [--encoding cp1252] [--csv]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")


@dataclass
class Stats:
    lines: int = 0
    words: int = 0
    chars: int = 0
    counts: Counter = field(default_factory=Counter)


def words(text: str) -> list[str]:
    """Split text into lower-cased words (see module docstring for the rule)."""
    return [w.casefold() for w in WORD.findall(text)]


def analyse(text: str, min_length: int = 1, stopwords: frozenset[str] = frozenset()) -> Stats:
    found = words(text)
    stats = Stats(lines=len(text.splitlines()), words=len(found), chars=len(text))
    stats.counts.update(w for w in found if len(w) >= min_length and w not in stopwords)
    return stats


def _read(name: str, encoding: str = "utf-8-sig") -> str | None:
    """Text of a file (or stdin for "-"); None if the file does not exist.

    Raises UnicodeDecodeError when the bytes do not match ``encoding``.
    """
    if name == "-":
        return sys.stdin.read()
    path = Path(name)
    if not path.is_file():
        return None
    return path.read_text(encoding=encoding)


def _decode_hint(name: str, exc: UnicodeDecodeError) -> str:
    return (
        f"wordfreq: {name} is not valid {exc.encoding} (byte 0x{exc.object[exc.start]:02x} at offset {exc.start}); "
        "try --encoding cp1252 or --encoding latin-1"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("inputs", nargs="+", help='text files, or "-" for stdin')
    p.add_argument("-n", "--top", type=int, default=10, help="how many words to list (default 10, 0 = none)")
    p.add_argument("--min-length", type=int, default=1, help="ignore words shorter than this")
    p.add_argument("--stopwords", type=Path, help="file with words to ignore, one per line")
    p.add_argument("--csv", action="store_true", help="print the word table as CSV (word,count)")
    p.add_argument("--encoding", default="utf-8-sig", help="text encoding of the input files (default UTF-8)")
    args = p.parse_args(argv)
    if args.top < 0 or args.min_length < 1:
        p.error("--top must be >= 0 and --min-length >= 1")
    try:
        "".encode(args.encoding)
    except LookupError:
        p.error(f"unknown encoding: {args.encoding}")

    stop: frozenset[str] = frozenset()
    if args.stopwords:
        if not args.stopwords.is_file():
            print(f"wordfreq: no such file: {args.stopwords}", file=sys.stderr)
            return 1
        try:
            stop = frozenset(words(args.stopwords.read_text(encoding=args.encoding)))
        except UnicodeDecodeError as exc:
            print(_decode_hint(str(args.stopwords), exc), file=sys.stderr)
            return 1

    total = Stats()
    for name in args.inputs:
        try:
            text = _read(name, args.encoding)
        except UnicodeDecodeError as exc:
            print(_decode_hint(name, exc), file=sys.stderr)
            return 1
        if text is None:
            print(f"wordfreq: no such file: {name}", file=sys.stderr)
            return 1
        s = analyse(text, args.min_length, stop)
        total.lines += s.lines
        total.words += s.words
        total.chars += s.chars
        total.counts.update(s.counts)

    # most_common keeps first-seen order for ties, so output is deterministic
    top = total.counts.most_common(args.top) if args.top else []
    if args.csv:
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(["word", "count"])
        writer.writerows(top)
        return 0
    print(f"lines {total.lines}  words {total.words}  chars {total.chars}  unique {len(total.counts)}")
    width = max((len(w) for w, _ in top), default=0)
    for word, count in top:
        print(f"{word:<{width}}  {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

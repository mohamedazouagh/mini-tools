"""fw2csv - convert a fixed-width text table (report, mainframe export) to CSV.

Column boundaries come from `-w 10,6,8` (one character width per column; the
last column always runs to the end of the line, so long values there are
never cut) or, by default, are detected: every character position that is
blank on all lines is a gap, and each run of non-blank positions starts a
column. `--gap 2`
needs at least two blank positions in a row before splitting, so headers
like "first name" stay one column. Cells are trimmed, tabs are expanded
(`--tabsize`, default 8), blank lines are skipped and `--skip N` drops
title lines at the top. The first remaining line is the header unless
`--names a,b,c` supplies one.

    python -m minitools.fw2csv report.txt [-w 10,6,8] [--gap 2] [--skip 2] [-d ';'] [-o out.csv]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def detect_starts(lines: list[str], gap: int = 1) -> list[int]:
    """Start position of each column: a non-blank run after at least ``gap`` all-blank positions."""
    width = max((len(line) for line in lines), default=0)
    used = [False] * width
    for line in lines:
        for i, ch in enumerate(line):
            if not ch.isspace():
                used[i] = True
    starts: list[int] = []
    blank_run = gap  # so the first used position always starts a column
    for i, u in enumerate(used):
        if u:
            if blank_run >= gap:
                starts.append(i)
            blank_run = 0
        else:
            blank_run += 1
    return starts


def starts_from_widths(widths: list[int]) -> list[int]:
    starts, pos = [], 0
    for w in widths:
        starts.append(pos)
        pos += w
    return starts


def split_line(line: str, starts: list[int]) -> list[str]:
    ends = starts[1:] + [None]
    return [line[s:e].strip() for s, e in zip(starts, ends)]


def _parse_widths(text: str) -> list[int]:
    try:
        widths = [int(w) for w in text.split(",") if w.strip()]
    except ValueError:
        raise ValueError(f"--widths must be whole numbers, got {text!r}") from None
    if not widths or any(w <= 0 for w in widths):
        raise ValueError(f"--widths must be positive whole numbers, got {text!r}")
    return widths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='text file, or "-" for stdin')
    p.add_argument("-w", "--widths", help="comma-separated column widths (default: detect from blank positions)")
    p.add_argument("--gap", type=int, default=1, help="blank positions needed between detected columns (default 1)")
    p.add_argument("--skip", type=int, default=0, help="drop this many lines at the top first (titles)")
    p.add_argument("--names", help="comma-separated header to use when the file has none")
    p.add_argument("--tabsize", type=int, default=8, help="expand tabs to this many spaces (default 8)")
    p.add_argument("-d", "--delimiter", default=",", help="output delimiter (default ,)")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)
    if len(args.delimiter) != 1:
        p.error("--delimiter must be a single character")
    if args.gap < 1 or args.skip < 0 or args.tabsize < 1:
        p.error("--gap and --tabsize must be at least 1, --skip at least 0")
    widths = None
    if args.widths:
        try:
            widths = _parse_widths(args.widths)
        except ValueError as exc:
            p.error(str(exc))

    if args.input == "-":
        text = sys.stdin.read()
    else:
        src = Path(args.input)
        if not src.is_file():
            print(f"fw2csv: no such file: {src}", file=sys.stderr)
            return 1
        text = src.read_text(encoding="utf-8-sig")
    lines = [line.rstrip("\r\n").expandtabs(args.tabsize) for line in text.splitlines()[args.skip:]]
    lines = [line for line in lines if line.strip()]
    if not lines:
        print("fw2csv: no data lines", file=sys.stderr)
        return 1

    starts = starts_from_widths(widths) if widths else detect_starts(lines, args.gap)
    if args.names:
        header = [n.strip() for n in args.names.split(",")]
        if len(header) != len(starts):
            print(f"fw2csv: --names has {len(header)} names but there are {len(starts)} columns", file=sys.stderr)
            return 2
        body = lines
    else:
        header, body = split_line(lines[0], starts), lines[1:]
        if any(not h for h in header):
            print(f"fw2csv: blank header cell in {header}; adjust --widths/--gap or pass --names", file=sys.stderr)
            return 2

    out = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.writer(out, delimiter=args.delimiter, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(split_line(line, starts) for line in body)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

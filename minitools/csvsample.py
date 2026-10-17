"""csvsample - reproducible random sample of the rows of a CSV.

Takes `-n N` rows (reservoir sampling: one pass, only N rows kept in memory,
so it works on files larger than RAM) or a `--frac 0.1` share of the rows,
always with the header. `--seed` makes the sample repeatable. Sampled rows
keep their original file order unless `--shuffle` is given. Blank lines are
skipped; asking for more rows than the file has returns every row.

    python -m minitools.csvsample big.csv -n 100 --seed 42 -o sample.csv
    python -m minitools.csvsample big.csv --frac 0.05 -d ';'
    python -m minitools.csvsample - -n 10 < big.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from collections.abc import Iterable
from pathlib import Path


def reservoir_sample(rows: Iterable[list[str]], n: int, rng: random.Random) -> list[list[str]]:
    """Uniform sample of ``n`` rows in file order (Algorithm R, one pass).

    Every row ends up in the sample with the same probability n / total.
    Returns all rows when there are at most ``n``.
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    picked: list[tuple[int, list[str]]] = []
    for i, row in enumerate(rows):
        if i < n:
            picked.append((i, row))
        else:
            j = rng.randint(0, i)
            if j < n:
                picked[j] = (i, row)
    return [row for _, row in sorted(picked, key=lambda p: p[0])]


def frac_sample(rows: list[list[str]], frac: float, rng: random.Random) -> list[list[str]]:
    """``round(frac * len(rows))`` rows chosen without replacement, in file order."""
    if not 0 <= frac <= 1:
        raise ValueError("frac must be between 0 and 1")
    k = round(frac * len(rows))
    keep = sorted(rng.sample(range(len(rows)), k))
    return [rows[i] for i in keep]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    size = p.add_mutually_exclusive_group(required=True)
    size.add_argument("-n", "--rows", type=int, help="number of rows to sample")
    size.add_argument("--frac", type=float, help="share of rows to sample, e.g. 0.1")
    p.add_argument("--seed", type=int, help="random seed for a repeatable sample")
    p.add_argument("--shuffle", action="store_true", help="output the sample in random order")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    p.add_argument("--force", action="store_true", help="overwrite --output if it exists")
    args = p.parse_args(argv)
    if args.rows is not None and args.rows < 0:
        p.error("--rows must be >= 0")
    if args.frac is not None and not 0 <= args.frac <= 1:
        p.error("--frac must be between 0 and 1")

    if args.input == "-":
        stream = sys.stdin
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvsample: no such file: {path}", file=sys.stderr)
            return 1
        stream = path.open(encoding="utf-8-sig", newline="")
    if args.output and Path(args.output).exists() and not args.force:
        print(f"csvsample: {args.output} exists (use --force to overwrite)", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)
    try:
        rows = (r for r in csv.reader(stream, delimiter=args.delimiter) if any(c.strip() for c in r))
        header = next(rows, None)
        if header is None:
            print("csvsample: input has no header row", file=sys.stderr)
            return 1
        sample = reservoir_sample(rows, args.rows, rng) if args.rows is not None else frac_sample(list(rows), args.frac, rng)
    finally:
        if stream is not sys.stdin:
            stream.close()
    if args.shuffle:
        rng.shuffle(sample)

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    w.writerow(header)
    w.writerows(sample)
    if args.output:
        Path(args.output).write_text(buf.getvalue(), encoding="utf-8", newline="")
        print(f"csvsample: wrote {len(sample)} rows to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

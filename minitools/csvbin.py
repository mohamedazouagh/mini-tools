"""csvbin - put a number column into ranges (bins) and write the range as a new column.

Reports often need "age group", "order size band" or "price bracket" instead
of the raw number. This adds a column next to the chosen one with the range
each value falls in, using edges you give:

    python -m minitools.csvbin people.csv -c age --edges 0,18,65 -o banded.csv
    python -m minitools.csvbin orders.csv -c amount --edges 0,50,250 --open-ends \
        --labels "refund,small,medium,large" --into size

Ranges are closed on the left and open on the right by default: with edges
0,18,65 the bins are "[0, 18)" and "[18, 65)", so 18 is an adult. `--right`
flips that to "(0, 18]" and "(18, 65]". A value outside all bins gets an
empty cell and is listed on stderr, unless `--open-ends` adds a bin below the
first edge ("< 0") and one at/above the last (">= 65"; "<= 0" and "> 65"
with --right). `--labels` replaces the generated names, one per bin in order.

Values are compared as exact decimals, so "18.0" equals the edge 18 and
"0.30000000000000004" really lands above an edge of 0.3. Cells must be plain
decimals ("12", "-0.5", ".75"; run csvnum first for "1.234,50"); others are
listed on stderr with their line number and `--strict` makes that an error (exit 1, nothing
written). Empty cells stay empty. The new column is named <column>_bin or
`--into NAME`, placed right after the source column. Bad edges, label counts,
unknown columns and name clashes exit 2. Reads a file or stdin ("-"),
writes stdout or -o.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import io
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

PLAIN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


class BinError(ValueError):
    pass


def parse_number(text: str) -> Decimal | None:
    s = text.strip()
    return Decimal(s) if PLAIN.fullmatch(s) else None


def parse_edges(text: str) -> tuple[list[Decimal], list[str]]:
    """Return (edges as Decimals, edges as written) for a comma-separated list."""
    written = [p.strip() for p in text.split(",") if p.strip()]
    if len(written) < 2:
        raise BinError("--edges needs at least two numbers, e.g. 0,18,65")
    edges = []
    for w in written:
        v = parse_number(w)
        if v is None:
            raise BinError(f"edge {w!r} is not a plain number")
        edges.append(v)
    if any(b <= a for a, b in zip(edges, edges[1:])):
        raise BinError("--edges must be strictly increasing")
    return edges, written


def make_labels(written: list[str], right: bool = False, open_ends: bool = False) -> list[str]:
    if right:
        labels = [f"({a}, {b}]" for a, b in zip(written, written[1:])]
    else:
        labels = [f"[{a}, {b})" for a, b in zip(written, written[1:])]
    if open_ends:
        low = f"<= {written[0]}" if right else f"< {written[0]}"
        high = f"> {written[-1]}" if right else f">= {written[-1]}"
        labels = [low, *labels, high]
    return labels


def bin_index(value: Decimal, edges: list[Decimal], right: bool = False, open_ends: bool = False) -> int | None:
    """Index of the bin ``value`` falls in, or None when it is outside every bin."""
    pos = bisect.bisect_left(edges, value) if right else bisect.bisect_right(edges, value)
    # pos = number of edges below value (strictly below with right=True, at or below otherwise)
    if open_ends:
        return pos
    if pos == 0 or pos == len(edges):
        return None
    return pos - 1


def bin_rows(
    rows: list[tuple[int, list[str]]],
    column: int,
    edges: list[Decimal],
    labels: list[str],
    right: bool = False,
    open_ends: bool = False,
) -> tuple[list[list[str]], list[tuple[int, str, str]], Counter]:
    """Return (rows with the bin inserted after ``column``, [(line, cell, reason)], label counts)."""
    out, problems, counts = [], [], Counter()
    for line, row in rows:
        new = list(row) + [""] * (column + 1 - len(row))
        cell = new[column]
        label = ""
        if cell.strip():
            value = parse_number(cell)
            if value is None:
                problems.append((line, cell, "not a plain number"))
            else:
                idx = bin_index(value, edges, right, open_ends)
                if idx is None:
                    problems.append((line, cell, "outside the edges"))
                else:
                    label = labels[idx]
                    counts[label] += 1
        new.insert(column + 1, label)
        out.append(new)
    return out, problems, counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--column", required=True, help="number column to bin")
    p.add_argument("--edges", required=True, help="comma-separated, strictly increasing bin edges")
    p.add_argument("--right", action="store_true", help="close bins on the right: (a, b]")
    p.add_argument("--open-ends", action="store_true", help="add a bin below the first and above the last edge")
    p.add_argument("--labels", help="comma-separated names, one per bin")
    p.add_argument("--into", help="name of the new column (default <column>_bin)")
    p.add_argument("--stats", action="store_true", help="print how many values fell in each bin to stderr")
    p.add_argument("--strict", action="store_true", help="fail (exit 1) on non-numeric or out-of-range cells")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    try:
        edges, written = parse_edges(args.edges)
        labels = make_labels(written, args.right, args.open_ends)
        if args.labels is not None:
            custom = [x.strip() for x in args.labels.split(",")]
            if len(custom) != len(labels):
                raise BinError(f"--labels has {len(custom)} name(s) but there are {len(labels)} bins")
            labels = custom
    except BinError as e:
        print(f"csvbin: {e}", file=sys.stderr)
        return 2

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvbin: no such file: {path}", file=sys.stderr)
            return 1
        if args.output and args.output.resolve() == path.resolve():
            print("csvbin: refusing to write over the input file", file=sys.stderr)
            return 2
        raw = path.read_text(encoding="utf-8-sig")

    reader = csv.reader(io.StringIO(raw), delimiter=args.delimiter)
    rows, start = [], 1
    for row in reader:
        if row:
            rows.append((start, row))
        start = reader.line_num + 1
    if not rows:
        print("csvbin: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0][1]]
    name = args.column.strip()
    if name not in header:
        print(f"csvbin: unknown column {name!r}; available: {', '.join(header)}", file=sys.stderr)
        return 2
    new_name = (args.into or f"{name}_bin").strip()
    if not new_name or new_name in header:
        print(f"csvbin: new column name {new_name!r} is empty or already exists", file=sys.stderr)
        return 2
    column = header.index(name)

    body, problems, counts = bin_rows(rows[1:], column, edges, labels, args.right, args.open_ends)
    for line, cell, reason in problems:
        print(f"csvbin: line {line}, {name}: {reason} {cell!r}", file=sys.stderr)
    if problems and args.strict:
        print(f"csvbin: {len(problems)} cell{'s' if len(problems) != 1 else ''} not binned, nothing written",
              file=sys.stderr)
        return 1
    if args.stats:
        for label in labels:
            print(f"{label}\t{counts[label]}", file=sys.stderr)

    new_header = list(header)
    new_header.insert(column + 1, new_name)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(new_header)
    writer.writerows(body)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

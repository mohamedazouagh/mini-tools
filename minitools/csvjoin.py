"""csvjoin - join two CSV files on a key column, like a SQL JOIN.

Every left row is combined with every right row whose key matches (keys are
compared after trimming spaces). --how left keeps left rows without a match,
with the right columns left empty. Right columns whose name clashes with a
left column get a "_right" suffix; the right key column is not repeated.

    python -m minitools.csvjoin orders.csv customers.csv -k customer_id [-o out.csv]
    python -m minitools.csvjoin a.csv b.csv -k id --right-key ID --how left -d ';'
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def read_csv(path: Path, delimiter: str) -> tuple[list[str], list[list[str]]]:
    """Header and non-blank rows of a CSV file (UTF-8, BOM tolerated)."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None) or []
        rows = [r for r in reader if any(cell.strip() for cell in r)]
    return header, rows


def _cell(row: list[str], i: int) -> str:
    return row[i] if i < len(row) else ""


def join_rows(
    left_header: list[str],
    left_rows: list[list[str]],
    right_header: list[str],
    right_rows: list[list[str]],
    left_key: str,
    right_key: str,
    how: str = "inner",
) -> tuple[list[str], list[list[str]], int]:
    """Join two tables; returns (header, rows, number of unmatched left rows).

    Output order follows the left table, then the right table's order for
    multiple matches. Raises KeyError for a missing key column and ValueError
    for an unknown ``how``.
    """
    if how not in ("inner", "left"):
        raise ValueError(f"how must be 'inner' or 'left', got {how!r}")
    if left_key not in left_header:
        raise KeyError(f"left file has no column {left_key!r}")
    if right_key not in right_header:
        raise KeyError(f"right file has no column {right_key!r}")
    li, ri = left_header.index(left_key), right_header.index(right_key)
    keep = [i for i in range(len(right_header)) if i != ri]
    taken = set(left_header)
    extra = [right_header[i] + "_right" if right_header[i] in taken else right_header[i] for i in keep]

    index: dict[str, list[list[str]]] = {}
    for row in right_rows:
        index.setdefault(_cell(row, ri).strip(), []).append(row)

    out: list[list[str]] = []
    unmatched = 0
    for row in left_rows:
        base = [_cell(row, i) for i in range(len(left_header))]
        matches = index.get(_cell(row, li).strip(), [])
        if not matches:
            unmatched += 1
            if how == "left":
                out.append(base + [""] * len(keep))
            continue
        for match in matches:
            out.append(base + [_cell(match, i) for i in keep])
    return left_header + extra, out, unmatched


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("left", type=Path, help="left CSV (its row order is kept)")
    p.add_argument("right", type=Path, help="right CSV (looked up by key)")
    p.add_argument("-k", "--key", required=True, help="key column in the left file (and right, unless --right-key)")
    p.add_argument("--right-key", help="key column name in the right file, if different")
    p.add_argument("--how", choices=("inner", "left"), default="inner", help="join type (default: inner)")
    p.add_argument("-o", "--output", type=Path, help="output CSV (default: stdout)")
    p.add_argument("-d", "--delimiter", default=",", help="field separator for input and output (default ',')")
    p.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = p.parse_args(argv)

    for path in (args.left, args.right):
        if not path.is_file():
            print(f"csvjoin: no such file: {path}", file=sys.stderr)
            return 1
    if args.output and args.output.exists() and not args.force:
        print(f"csvjoin: {args.output} already exists; use --force to overwrite", file=sys.stderr)
        return 1
    lh, lrows = read_csv(args.left, args.delimiter)
    rh, rrows = read_csv(args.right, args.delimiter)
    try:
        header, rows, unmatched = join_rows(lh, lrows, rh, rrows, args.key, args.right_key or args.key, args.how)
    except KeyError as exc:
        print(f"csvjoin: {exc.args[0]}", file=sys.stderr)
        return 1

    if args.output:
        f = args.output.open("w", encoding="utf-8", newline="")
    else:
        f = sys.stdout
    try:
        w = csv.writer(f, delimiter=args.delimiter, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    finally:
        if args.output:
            f.close()
    print(f"csvjoin: {len(rows)} rows written, {unmatched} left rows without a match", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

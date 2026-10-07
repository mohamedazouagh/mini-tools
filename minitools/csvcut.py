"""csvcut - keep, reorder or drop CSV columns by name.

`-c a,b` keeps only those columns in that order (so it also reorders);
`-x a,b` drops them and keeps everything else in the original order. Unknown
column names are an error that lists the real headers, instead of silently
producing an empty column. Reads a file or stdin ("-"), writes stdout or -o.

    python -m minitools.csvcut in.csv -c email,name [-o out.csv] [-d ';']
    python -m minitools.csvcut in.csv -x notes,internal_id
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


class ColumnError(ValueError):
    pass


def _names(spec: str) -> list[str]:
    return [n.strip() for n in spec.split(",") if n.strip()]


def plan_columns(header: list[str], keep: list[str] | None = None, drop: list[str] | None = None) -> list[int]:
    """Indexes of the output columns, in output order.

    Raises ColumnError for names that are not in the header, or when nothing
    would be left.
    """
    wanted = keep if keep is not None else drop or []
    missing = [n for n in wanted if n not in header]
    if missing:
        raise ColumnError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    if keep is not None:
        idx = [header.index(n) for n in keep]
    else:
        dropped = set(wanted)
        idx = [i for i, n in enumerate(header) if n not in dropped]
    if not idx:
        raise ColumnError("no columns left to write")
    return idx


def cut_rows(rows: list[list[str]], idx: list[int]) -> list[list[str]]:
    """Pick columns from each row; short rows are padded with empty cells."""
    return [[row[i] if i < len(row) else "" for i in idx] for row in rows]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--columns", help="comma-separated columns to keep, in this order")
    group.add_argument("-x", "--exclude", help="comma-separated columns to drop")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvcut: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvcut: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        idx = plan_columns(
            header,
            keep=_names(args.columns) if args.columns else None,
            drop=_names(args.exclude) if args.exclude else None,
        )
    except ColumnError as e:
        print(f"csvcut: {e}", file=sys.stderr)
        return 2

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow([header[i] for i in idx])
    writer.writerows(cut_rows(rows[1:], idx))
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

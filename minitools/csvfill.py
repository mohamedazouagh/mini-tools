"""csvfill - fill blank CSV cells down from the row above, or with a fixed value.

Reports exported from spreadsheets often show a group label only on its first
row (merged cells, "repeat item labels" switched off), which breaks sorting,
filtering and grouping. `-c region,store` copies the last non-blank value of
each listed column into the blank cells below it; `--all` does every column.
`--value TEXT` writes TEXT into blank cells instead of filling down. Cells that
contain only spaces count as blank. Blank cells before the first value of a
column stay blank (there is nothing to copy).

`--within region` stops values leaking from one group into the next: whenever
the (filled) value of the region column changes, the remembered values of the
other columns are forgotten, so a new region whose first store cell is blank
stays blank instead of inheriting the previous region's last store.

    python -m minitools.csvfill report.csv -c region,store -o tidy.csv
    python -m minitools.csvfill report.csv --all -d ';'
    python -m minitools.csvfill scores.csv -c score --value 0 --stats
    python -m minitools.csvfill report.csv -c region,store --within region
    python -m minitools.csvfill subtotals.csv -c region --up

`--up` fills from the next non-blank value below instead, for reports that
print the group label on the last row of each group (next to a subtotal).
Blank cells after the last value stay blank; `--within` works the same way.

Reads a file or stdin ("-"), writes stdout or -o. Unknown column names list the
real headers (exit 2).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


class ColumnError(ValueError):
    pass


def resolve_columns(header: list[str], names: list[str]) -> list[int]:
    missing = [n for n in names if n not in header]
    if missing:
        raise ColumnError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    return [header.index(n) for n in names]


def fill_rows(
    rows: list[list[str]], idx: list[int], value: str | None = None, within: int | None = None
) -> tuple[list[list[str]], int]:
    """Fill blank cells in the given column indexes.

    With ``value`` None, each blank cell gets the last non-blank value above it
    in the same column; otherwise it gets ``value``. With ``within`` set to a
    column index, filled-down values are forgotten whenever that column's value
    (after its own fill) changes, so they never cross into the next group.
    Short rows are padded so the filled columns exist. Returns (new rows,
    number of cells filled).
    """
    last: dict[int, str] = {}
    filled = 0
    out: list[list[str]] = []
    width = max(idx + ([within] if within is not None else []), default=-1) + 1
    # Fill the group column first so the group of each row is known before the rest.
    order = ([within] if within in idx else []) + [i for i in idx if i != within]
    group: str | None = None
    for row in rows:
        new = row + [""] * (width - len(row)) if len(row) < width else list(row)
        for i in order:
            if i != within and within is not None:
                current = new[within].strip()
                if current != group:
                    group = current
                    last = {k: v for k, v in last.items() if k == within}
            if new[i].strip():
                last[i] = new[i]
                continue
            replacement = value if value is not None else last.get(i)
            if replacement is not None:
                new[i] = replacement
                filled += 1
        out.append(new)
    return out, filled


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument("-c", "--columns", help="comma-separated columns to fill")
    which.add_argument("--all", action="store_true", help="fill every column")
    p.add_argument("--value", help="write this into blank cells instead of filling down")
    p.add_argument("--within", metavar="COLUMN", help="restart filling down whenever this column's value changes")
    p.add_argument("--up", action="store_true", help="fill from the next non-blank value below instead of above")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    p.add_argument("--stats", action="store_true", help="print how many cells were filled to stderr")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvfill: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvfill: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        if args.all:
            idx = list(range(len(header)))
        else:
            idx = resolve_columns(header, [n.strip() for n in args.columns.split(",") if n.strip()])
        within = resolve_columns(header, [args.within.strip()])[0] if args.within else None
    except ColumnError as e:
        print(f"csvfill: {e}", file=sys.stderr)
        return 2
    if within is not None and args.value is not None:
        print("csvfill: --within only applies to filling down, not with --value", file=sys.stderr)
        return 2

    if args.up and args.value is not None:
        print("csvfill: --up only applies to filling, not with --value", file=sys.stderr)
        return 2

    if args.up:
        body, filled = fill_rows(rows[:0:-1], idx, None, within)
        body.reverse()
    else:
        body, filled = fill_rows(rows[1:], idx, args.value, within)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(body)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    if args.stats:
        print(f"csvfill: filled {filled} cell{'s' if filled != 1 else ''} in {len(body)} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

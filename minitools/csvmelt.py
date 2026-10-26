"""csvmelt - turn a wide CSV (one column per month/item) into long rows.

Spreadsheet reports often keep one row per entity and one column per period:
`store,jan,feb,mar`. Grouping, filtering or charting is much easier when the
data is "long": one row per store and month with a single value column.
`-i store` names the identifier column(s) that are repeated on every output
row; the value columns are all the others, or only those given with `-v`.
Each value column becomes one output row with the column name in a
`variable` column and the cell in a `value` column (rename both with
`--var-name` / `--value-name`). `-v` also takes glob patterns such as
`"2026-*"` so sheets with many period columns and some extra info columns
don't need every name typed out. Output is grouped per input row, value
columns in the order given. `--skip-blank` leaves out empty (or space-only)
cells instead of writing rows with an empty value.

    python -m minitools.csvmelt sales_wide.csv -i store --var-name month --value-name sales -o sales_long.csv
    python -m minitools.csvmelt scores.csv -i id,name -v q1,q2 --skip-blank -d ';'

Reads a file or stdin ("-"), writes stdout or -o. Unknown column names list the
real headers, and a column used both as id and value is rejected (exit 2).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from fnmatch import fnmatchcase
from pathlib import Path


class ColumnError(ValueError):
    pass


def _names(spec: str | None) -> list[str]:
    return [n.strip() for n in (spec or "").split(",") if n.strip()]


def _expand_patterns(header: list[str], ids: list[str], values: list[str]) -> list[str]:
    """Replace glob patterns (`2026-*`, `q?`) in the value list by the matching non-id headers, in header order."""
    out: list[str] = []
    for name in values:
        if not any(ch in name for ch in "*?["):
            out.append(name)
            continue
        matches = [h for h in header if h not in ids and fnmatchcase(h, name)]
        if not matches:
            raise ColumnError(f"pattern {name!r} matches no column; available: {', '.join(header)}")
        out.extend(m for m in matches if m not in out)
    return out


def plan_columns(header: list[str], ids: list[str], values: list[str]) -> tuple[list[int], list[int]]:
    """Resolve id and value column names to indexes (values default to every non-id column).

    Value names may be glob patterns (`-v "2026-*"`), matched case-sensitively
    against the headers; patterns never pick id columns, and a column matched
    twice is only melted once.
    """
    if len(set(header)) != len(header):
        dupes = sorted({h for h in header if header.count(h) > 1})
        raise ColumnError(f"duplicate header(s): {', '.join(dupes)}")
    values = _expand_patterns(header, ids, values)
    missing = [n for n in ids + values if n not in header]
    if missing:
        raise ColumnError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    both = [n for n in values if n in ids]
    if both:
        raise ColumnError(f"column(s) used as both id and value: {', '.join(both)}")
    if not values:
        values = [h for h in header if h not in ids]
    if not values:
        raise ColumnError("no value columns left to melt")
    return [header.index(n) for n in ids], [header.index(n) for n in values]


def melt(
    header: list[str],
    rows: list[list[str]],
    id_idx: list[int],
    value_idx: list[int],
    var_name: str = "variable",
    value_name: str = "value",
    skip_blank: bool = False,
) -> list[list[str]]:
    """Long-format rows, header first. Short rows count as having blank cells."""
    out = [[header[i] for i in id_idx] + [var_name, value_name]]
    for row in rows:
        ids = [row[i] if i < len(row) else "" for i in id_idx]
        for i in value_idx:
            cell = row[i] if i < len(row) else ""
            if skip_blank and not cell.strip():
                continue
            out.append(ids + [header[i], cell])
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-i", "--id", help="comma-separated id column(s) repeated on every row")
    p.add_argument("-v", "--values",
                   help='comma-separated columns or glob patterns to melt, e.g. "2026-*" (default: all non-id columns)')
    p.add_argument("--var-name", default="variable", help="name of the column holding the old header")
    p.add_argument("--value-name", default="value", help="name of the column holding the cell")
    p.add_argument("--skip-blank", action="store_true", help="drop rows whose value cell is empty")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvmelt: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvmelt: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        id_idx, value_idx = plan_columns(header, _names(args.id), _names(args.values))
        if args.var_name == args.value_name or {args.var_name, args.value_name} & {header[i] for i in id_idx}:
            raise ColumnError("--var-name and --value-name must differ from each other and from the id columns")
    except ColumnError as e:
        print(f"csvmelt: {e}", file=sys.stderr)
        return 2

    out = melt(header, rows[1:], id_idx, value_idx, args.var_name, args.value_name, args.skip_blank)
    buf = io.StringIO()
    csv.writer(buf, delimiter=args.delimiter, lineterminator="\n").writerows(out)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

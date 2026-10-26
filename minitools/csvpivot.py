"""csvpivot - turn long CSV rows (id, variable, value) back into a wide table.

The inverse of csvmelt: `-i store` names the identifier column(s) that make
one output row each, `-c month` the column whose values become the new
headers, and `-v sales` the column whose cells fill the table. Output rows
and new columns keep the order in which they first appear in the input.
Missing combinations are left empty, or filled with `--fill 0`.

A (row id, column) pair that appears twice is an error by default, because
silently picking one hides a data problem; `--keep first` / `--keep last`
choose one on purpose. Keys are compared after trimming surrounding spaces.

    python -m minitools.csvpivot sales_long.csv -i store -c month -v sales -o sales_wide.csv
    python -m minitools.csvpivot scores.csv -i id,name -c question -v score --fill 0 -d ';'

Reads a file or stdin ("-"), writes stdout or -o. Unknown column names list the
real headers; duplicates, blank new headers or headers that clash with an id
column are rejected (exit 2).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


class PivotError(ValueError):
    pass


def _names(spec: str | None) -> list[str]:
    return [n.strip() for n in (spec or "").split(",") if n.strip()]


def plan_columns(header: list[str], ids: list[str], column: str, value: str) -> tuple[list[int], int, int]:
    """Resolve id, column and value names to indexes."""
    if len(set(header)) != len(header):
        dupes = sorted({h for h in header if header.count(h) > 1})
        raise PivotError(f"duplicate header(s): {', '.join(dupes)}")
    missing = [n for n in ids + [column, value] if n not in header]
    if missing:
        raise PivotError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    if column == value or column in ids or value in ids:
        raise PivotError("id, --column and --value must all be different columns")
    return [header.index(n) for n in ids], header.index(column), header.index(value)


def pivot(
    header: list[str],
    rows: list[list[str]],
    id_idx: list[int],
    col_idx: int,
    val_idx: int,
    keep: str = "error",
    fill: str = "",
    line_numbers: list[int] | None = None,
) -> list[list[str]]:
    """Wide rows, header first. Short rows count as having blank cells.

    ``line_numbers`` gives the file line each row ends on, for error messages;
    by default rows are assumed to follow the header on lines 2, 3, ...
    """

    def cell(row: list[str], i: int) -> str:
        return row[i] if i < len(row) else ""

    new_cols: list[str] = []
    table: dict[tuple[str, ...], dict[str, str]] = {}
    for n, row in zip(line_numbers or range(2, len(rows) + 2), rows, strict=True):
        key = tuple(cell(row, i).strip() for i in id_idx)
        col = cell(row, col_idx).strip()
        if not col:
            raise PivotError(f"line {n}: blank value in column {header[col_idx]!r} can't become a header")
        cells = table.setdefault(key, {})
        if col in cells:
            if keep == "error":
                label = ", ".join(key) or "(all rows)"
                raise PivotError(f"line {n}: duplicate entry for {label} / {col}; use --keep first or --keep last")
            if keep == "first":
                continue
        if col not in new_cols:
            new_cols.append(col)
        cells[col] = cell(row, val_idx)
    id_names = [header[i] for i in id_idx]
    clash = [c for c in new_cols if c in id_names]
    if clash:
        raise PivotError(f"new column(s) clash with id columns: {', '.join(clash)}")
    out = [id_names + new_cols]
    for key, cells in table.items():
        out.append(list(key) + [cells.get(c, fill) for c in new_cols])
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-i", "--id", help="comma-separated id column(s); one output row per distinct id")
    p.add_argument("-c", "--column", required=True, help="column whose values become the new headers")
    p.add_argument("-v", "--value", required=True, help="column whose cells fill the table")
    p.add_argument("--keep", choices=["error", "first", "last"], default="error",
                   help="what to do when an id/column pair repeats (default: error)")
    p.add_argument("--fill", default="", help="text for missing combinations (default: empty)")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvpivot: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    reader = csv.reader(io.StringIO(raw), delimiter=args.delimiter)
    numbered = [(reader.line_num, r) for r in reader if r]  # blank lines skipped, real line numbers kept
    if not numbered:
        print("csvpivot: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in numbered[0][1]]
    body = numbered[1:]
    try:
        id_idx, col_idx, val_idx = plan_columns(header, _names(args.id), args.column.strip(), args.value.strip())
        out = pivot(header, [r for _, r in body], id_idx, col_idx, val_idx, args.keep, args.fill,
                    line_numbers=[n for n, _ in body])
    except PivotError as e:
        print(f"csvpivot: {e}", file=sys.stderr)
        return 2

    buf = io.StringIO()
    csv.writer(buf, delimiter=args.delimiter, lineterminator="\n").writerows(out)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

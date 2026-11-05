"""csvmergecol - combine several CSV columns into one new column.

The inverse of csvsplitcol: `first,last` to a full name, `street,number,city`
to one address line, `date,time` to a timestamp, `prefix,id` to a key.
`-c first,last --into name` replaces the source columns with `name`, placed at
the position of the first source column; `--keep` keeps the sources and adds
`name` right after the last of them. Values are trimmed and joined with
`--sep` (default one space) in the order given to `-c`.

Blank parts are skipped by default, so "Ana" + "" gives "Ana", not "Ana ";
`--keep-blank` keeps them (useful for fixed positions like `a;;c`). A row whose
sources are all blank gives an empty cell.

    python -m minitools.csvmergecol people.csv -c first,last --into name
    python -m minitools.csvmergecol log.csv -c date,time --into ts --sep "T" --keep
    python -m minitools.csvmergecol addr.csv -c street,number,city --into address --sep ", " -d ';'

Reads a file or stdin ("-"), writes stdout or -o. Unknown columns list the real
headers; repeated sources, fewer than two sources, or a new name clashing with
a column that stays are rejected (exit 2).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


class ColumnError(ValueError):
    pass


def merge_cells(cells: list[str], sep: str = " ", keep_blank: bool = False) -> str:
    """Join trimmed ``cells`` with ``sep``; blank cells are dropped unless ``keep_blank``."""
    parts = [c.strip() for c in cells]
    if not keep_blank:
        parts = [p for p in parts if p]
    elif not any(parts):
        return ""
    return sep.join(parts)


def plan_header(header: list[str], columns: list[str], into: str, keep: bool) -> tuple[list[int], list[str]]:
    """Return (source indexes in -c order, new header); raise ColumnError on bad names."""
    unknown = [c for c in columns if c not in header]
    if unknown:
        raise ColumnError(f"unknown column(s): {', '.join(unknown)}; available: {', '.join(header)}")
    repeated = sorted({c for c in columns if columns.count(c) > 1})
    if repeated:
        raise ColumnError(f"-c repeats: {', '.join(repeated)}")
    if len(columns) < 2:
        raise ColumnError("-c needs at least two columns to merge")
    if not into:
        raise ColumnError("--into needs a non-empty column name")
    idxs = [header.index(c) for c in columns]
    staying = header if keep else [h for i, h in enumerate(header) if i not in idxs]
    if into in staying:
        raise ColumnError(f"new column already exists: {into}")
    return idxs, _place(header, idxs, into, keep)


def _place(row: list[str], idxs: list[int], value: str, keep: bool) -> list[str]:
    """Insert ``value`` after the last source (keep) or at the first source's slot (replace)."""
    if keep:
        at = max(idxs) + 1
        return row[:at] + [value] + row[at:]
    first = min(idxs)
    return row[:first] + [value] + [v for i, v in enumerate(row) if i > first and i not in idxs]


def merge_rows(
    rows: list[list[str]], idxs: list[int], sep: str = " ", keep_blank: bool = False, keep: bool = False
) -> list[list[str]]:
    """Merge the ``idxs`` columns of every row (short rows padded first)."""
    out: list[list[str]] = []
    width = max(idxs) + 1
    for row in rows:
        if len(row) < width:
            row = row + [""] * (width - len(row))
        value = merge_cells([row[i] for i in idxs], sep, keep_blank)
        out.append(_place(row, idxs, value, keep))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--columns", required=True, help="comma-separated columns to merge, in output order")
    p.add_argument("--into", required=True, help="name of the new column")
    p.add_argument("--sep", default=" ", help="text between the parts (default: one space)")
    p.add_argument("--keep-blank", action="store_true", help="keep blank parts (consecutive separators)")
    p.add_argument("--keep", action="store_true", help="keep the source columns; new column goes after them")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvmergecol: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvmergecol: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    columns = [c.strip() for c in args.columns.split(",")]
    try:
        idxs, new_header = plan_header(header, columns, args.into.strip(), args.keep)
    except ColumnError as e:
        print(f"csvmergecol: {e}", file=sys.stderr)
        return 2

    body = merge_rows(rows[1:], idxs, args.sep, args.keep_blank, args.keep)
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

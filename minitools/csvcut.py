"""csvcut - keep, reorder or drop CSV columns by name.

`-c a,b` keeps only those columns in that order (so it also reorders);
`-x a,b` drops them and keeps everything else in the original order. Unknown
column names are an error that lists the real headers, instead of silently
producing an empty column. Reads a file or stdin ("-"), writes stdout or -o.

    python -m minitools.csvcut in.csv -c email,name [-o out.csv] [-d ';']
    python -m minitools.csvcut in.csv -x notes,internal_id
    python -m minitools.csvcut in.csv -c email,id -r email=Email -r id=customer_id
    python -m minitools.csvcut legacy.csv -c name,city --encoding cp1252 -o utf8.csv

Input is read as UTF-8 (a BOM is fine) unless --encoding says otherwise, so a
legacy Excel export can be cut and converted to UTF-8 in one step; undecodable
input gives a short error with the byte offset instead of a traceback.
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


def rename_header(header: list[str], specs: list[str]) -> list[str]:
    """Apply ``old=new`` renames to an output header.

    Raises ColumnError for a malformed spec, a name that is not in the header,
    or a rename that would leave two columns with the same name.
    """
    mapping: dict[str, str] = {}
    for spec in specs:
        old, sep, new = spec.partition("=")
        old, new = old.strip(), new.strip()
        if not sep or not old or not new:
            raise ColumnError(f"bad --rename {spec!r}; use old=new")
        if old not in header:
            raise ColumnError(f"cannot rename {old!r}: not in output columns ({', '.join(header)})")
        mapping[old] = new
    out = [mapping.get(h, h) for h in header]
    dupes = sorted({h for h in out if out.count(h) > 1})
    if dupes:
        raise ColumnError(f"rename would duplicate column name(s): {', '.join(dupes)}")
    return out


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
    p.add_argument(
        "-r", "--rename", action="append", default=[], metavar="OLD=NEW", help="rename an output column (repeatable)"
    )
    p.add_argument(
        "--encoding", default="utf-8-sig", help="encoding of the input file, e.g. cp1252 (default UTF-8); output is UTF-8"
    )
    args = p.parse_args(argv)
    try:
        "".encode(args.encoding)
    except LookupError:
        p.error(f"unknown encoding: {args.encoding}")

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvcut: no such file: {path}", file=sys.stderr)
            return 1
        try:
            raw = path.read_text(encoding=args.encoding)
        except UnicodeDecodeError as exc:
            print(
                f"csvcut: {path} is not valid {exc.encoding} (byte 0x{exc.object[exc.start]:02x} at offset "
                f"{exc.start}); try --encoding cp1252 or --encoding latin-1",
                file=sys.stderr,
            )
            return 1

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
        out_header = rename_header([header[i] for i in idx], args.rename)
    except ColumnError as e:
        print(f"csvcut: {e}", file=sys.stderr)
        return 2

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(out_header)
    writer.writerows(cut_rows(rows[1:], idx))
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

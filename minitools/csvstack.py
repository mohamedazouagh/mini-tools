"""csvstack - append several CSV files into one, writing the header only once.

By default every file must have the same columns (in any order; rows are
re-ordered to match the first file). With `--union` the output gets every
column seen in any file, in first-seen order, and cells a file does not have
are left empty. `--source NAME` adds a column with the file each row came
from, which keeps monthly or per-region exports traceable after merging.
Blank lines are skipped and short rows are padded; rows longer than their
header are rejected instead of silently losing data.

    python -m minitools.csvstack jan.csv feb.csv mar.csv -o q1.csv
    python -m minitools.csvstack exports/*.csv --union --source file -d ';'
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


class StackError(ValueError):
    pass


def read_table(text: str, delimiter: str = ",", name: str = "input") -> tuple[list[str], list[list[str]]]:
    """Header and data rows of one CSV text; blank lines dropped, short rows padded."""
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
    if not rows:
        raise StackError(f"{name}: no header row")
    header = [h.strip() for h in rows[0]]
    dupes = sorted({h for h in header if header.count(h) > 1})
    if dupes:
        raise StackError(f"{name}: duplicate column name(s): {', '.join(dupes)}")
    data = []
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) > len(header):
            raise StackError(f"{name}: row {line_no} has {len(row)} cells but the header has {len(header)}")
        data.append(row + [""] * (len(header) - len(row)))
    return header, data


def stack(
    tables: list[tuple[str, list[str], list[list[str]]]],
    union: bool = False,
    source: str | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Combine (name, header, rows) tables into one header and row list.

    Without ``union`` every table must have exactly the columns of the first
    one (order may differ). ``source`` adds a column holding each row's table
    name; it must not clash with an existing column.
    """
    if not tables:
        raise StackError("no input files")
    first_name, columns, _ = tables[0]
    columns = list(columns)
    for name, header, _ in tables[1:]:
        if union:
            columns += [h for h in header if h not in columns]
        elif set(header) != set(columns):
            missing = [c for c in columns if c not in header]
            extra = [h for h in header if h not in columns]
            parts = []
            if missing:
                parts.append(f"missing {', '.join(missing)}")
            if extra:
                parts.append(f"extra {', '.join(extra)}")
            raise StackError(
                f"{name}: columns differ from {first_name} ({'; '.join(parts)}); use --union to combine anyway"
            )
    if source is not None:
        if source in columns:
            raise StackError(f"--source column {source!r} already exists in the input")
        columns = [source] + columns
    out = []
    for name, header, rows in tables:
        pos = {h: i for i, h in enumerate(header)}
        for row in rows:
            cells = [row[pos[c]] if c in pos else "" for c in columns]
            if source is not None:
                cells[0] = name
            out.append(cells)
    return columns, out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("inputs", nargs="+", help="CSV files to stack, in order")
    p.add_argument("--union", action="store_true", help="allow different columns; fill missing cells with empty")
    p.add_argument("--source", metavar="NAME", help="add a first column NAME with each row's file name")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter for input and output (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    tables = []
    try:
        for raw_path in args.inputs:
            path = Path(raw_path)
            if not path.is_file():
                raise StackError(f"no such file: {path}")
            if args.output and path.resolve() == args.output.resolve():
                raise StackError(f"output {path} is also an input")
            header, rows = read_table(path.read_text(encoding="utf-8-sig"), args.delimiter, path.name)
            tables.append((path.name, header, rows))
        columns, rows = stack(tables, union=args.union, source=args.source)
    except StackError as e:
        print(f"csvstack: {e}", file=sys.stderr)
        return 2

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    print(f"csvstack: {len(rows)} row(s) from {len(tables)} file(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

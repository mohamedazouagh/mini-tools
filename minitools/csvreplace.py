"""csvreplace - find and replace with a regex inside chosen CSV columns only.

A plain text editor's search-and-replace also hits headers and every other
column; this only touches the cells of the columns you name, and the CSV
quoting stays valid whatever the replacement contains.

    python -m minitools.csvreplace contacts.csv -c phone -p "[^0-9+]" -r ""
    python -m minitools.csvreplace orders.csv -c country -p "^(nl|holland)$" -r NL -i -o fixed.csv
    python -m minitools.csvreplace prices.csv --all -p "." -r "," --literal -d ";"

`-p` is a Python regex (groups usable as `\\1` or `\\g<name>` in `-r`);
`--literal` treats it as plain text instead. `--whole` only replaces cells
the pattern matches completely (like a lookup: `NL` but not `NLD`). `-i`
ignores case. `--count` prints how many cells changed per column on stderr.

Reads a file or stdin ("-"), writes stdout or -o. Unknown column names list the
real headers; a bad pattern or group reference fails with exit 2.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path


class ColumnError(ValueError):
    pass


def pick_columns(names: list[str], header: list[str]) -> list[int]:
    """Indexes of the comma-separated names in ``names``, in header order, no repeats."""
    wanted = [n.strip() for part in names for n in part.split(",") if n.strip()]
    unknown = [n for n in wanted if n not in header]
    if unknown:
        raise ColumnError(f"unknown column(s): {', '.join(unknown)}; available: {', '.join(header)}")
    return sorted({header.index(n) for n in wanted})


def compile_pattern(pattern: str, literal: bool = False, ignore_case: bool = False, whole: bool = False) -> re.Pattern:
    body = re.escape(pattern) if literal else pattern
    if whole:
        body = f"(?:{body})"
    return re.compile(body, re.IGNORECASE if ignore_case else 0)


def replace_rows(
    rows: list[list[str]], columns: list[int], rx: re.Pattern, replacement: str,
    literal: bool = False, whole: bool = False,
) -> tuple[list[list[str]], dict[int, int]]:
    """Return (new rows, {column index: cells changed}). Short rows are left short."""
    repl = (lambda _m: replacement) if literal else replacement
    changed = {i: 0 for i in columns}
    out = []
    for row in rows:
        new = list(row)
        for i in columns:
            if i >= len(new):
                continue
            cell = new[i]
            if whole:
                m = rx.fullmatch(cell)
                value = (m.expand(replacement) if not literal else replacement) if m else cell
            else:
                value = rx.sub(repl, cell)
            if value != cell:
                new[i] = value
                changed[i] += 1
        out.append(new)
    return out, changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("-c", "--columns", action="append", metavar="NAMES",
                        help="comma-separated column names to edit; repeatable")
    target.add_argument("--all", action="store_true", help="edit every column (header row is never changed)")
    p.add_argument("-p", "--pattern", required=True, help="regex to find (plain text with --literal)")
    p.add_argument("-r", "--replacement", default="", help="replacement text, \\1 / \\g<name> allowed (default: delete)")
    p.add_argument("--literal", action="store_true", help="treat pattern and replacement as plain text")
    p.add_argument("--whole", action="store_true", help="only replace cells the pattern matches completely")
    p.add_argument("-i", "--ignore-case", action="store_true", help="case-insensitive matching")
    p.add_argument("--count", action="store_true", help="print changed cells per column on stderr")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    try:
        rx = compile_pattern(args.pattern, args.literal, args.ignore_case, args.whole)
    except re.error as e:
        print(f"csvreplace: bad pattern: {e}", file=sys.stderr)
        return 2
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvreplace: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvreplace: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        columns = list(range(len(header))) if args.all else pick_columns(args.columns, header)
    except ColumnError as e:
        print(f"csvreplace: {e}", file=sys.stderr)
        return 2
    try:
        body, changed = replace_rows(rows[1:], columns, rx, args.replacement, args.literal, args.whole)
    except (re.error, IndexError) as e:
        print(f"csvreplace: bad replacement: {e}", file=sys.stderr)
        return 2

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(body)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    if args.count:
        for i in columns:
            print(f"{header[i]}: {changed[i]} cell{'s' if changed[i] != 1 else ''} changed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

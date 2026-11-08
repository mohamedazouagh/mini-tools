"""csvround - round number columns in a CSV to a fixed number of decimals.

Computed exports often carry float noise ("12.299999999", "0.30000000000000004")
or more decimals than a report should show. This rounds the chosen columns
with exact decimal arithmetic, so 2.675 really becomes 2.68 (float round()
gives 2.67), and writes every value with exactly N decimals ("12.5" -> "12.50").

    python -m minitools.csvround sales.csv -c amount,vat -p 2 -o rounded.csv
    python -m minitools.csvround stats.csv -c mean --mode half-even -p 1 --strict

`--mode` picks the rule for ties and cut-offs: `half-up` (default, 0.5 away
from zero, the school rule), `half-even` (banker's rounding, no upward bias
over many values), `down` (truncate toward zero), `floor` and `ceiling`.
`-p 0` gives whole numbers; a negative -p rounds to tens, hundreds, ...

Cells must be plain decimals ("1234.5", "-0.25", ".5"); for "1.234,50" or
"€ 12" run csvnum first. Other cells are left unchanged and listed on stderr
with their line number; `--strict` makes that an error (exit 1, nothing
written). Empty cells stay empty, "-0.00" is written as "0.00". Unknown
columns exit 2. Reads a file or stdin ("-"), writes stdout or -o.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Decimal,
    localcontext,
)
from pathlib import Path

MODES = {
    "half-up": ROUND_HALF_UP,
    "half-even": ROUND_HALF_EVEN,
    "down": ROUND_DOWN,
    "floor": ROUND_FLOOR,
    "ceiling": ROUND_CEILING,
}
PLAIN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


class ColumnError(ValueError):
    pass


def round_cell(text: str, places: int = 2, mode: str = "half-up") -> str | None:
    """Round one plain decimal string; None when the cell is not a plain decimal."""
    s = text.strip()
    if not PLAIN.fullmatch(s):
        return None
    value = Decimal(s)
    exp = Decimal(1).scaleb(-places)  # 0.01 for places=2, 1E+1 for places=-1
    with localcontext() as ctx:
        ctx.prec = max(len(s) + abs(places) + 2, 28)  # never lose digits while quantizing
        rounded = value.quantize(exp, rounding=MODES[mode])
    if rounded == 0:
        rounded = abs(rounded)  # "-0.00" -> "0.00"
    return format(rounded, "f")  # "f" also expands 1.2E+2 (negative places) to "120"


def pick_columns(names: list[str], header: list[str]) -> list[int]:
    wanted = [n.strip() for part in names for n in part.split(",") if n.strip()]
    unknown = [n for n in wanted if n not in header]
    if unknown:
        raise ColumnError(f"unknown column(s): {', '.join(unknown)}; available: {', '.join(header)}")
    if not wanted:
        raise ColumnError("no columns given")
    return sorted({header.index(n) for n in wanted})


def round_rows(
    rows: list[tuple[int, list[str]]], columns: list[int], places: int = 2, mode: str = "half-up"
) -> tuple[list[list[str]], list[tuple[int, int, str]]]:
    """Return (new rows, [(line, column index, cell) that are not plain decimals])."""
    out, bad = [], []
    for line, row in rows:
        new = list(row)
        for i in columns:
            if i >= len(new) or not new[i].strip():
                continue
            value = round_cell(new[i], places, mode)
            if value is None:
                bad.append((line, i, new[i]))
            else:
                new[i] = value
        out.append(new)
    return out, bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--columns", action="append", required=True, metavar="NAMES",
                   help="comma-separated number columns; repeatable")
    p.add_argument("-p", "--places", type=int, default=2, help="decimals to keep (default 2)")
    p.add_argument("--mode", choices=list(MODES), default="half-up",
                   help="rounding rule (default half-up)")
    p.add_argument("--strict", action="store_true", help="fail (exit 1) if any cell is not a number")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvround: no such file: {path}", file=sys.stderr)
            return 1
        if args.output and args.output.resolve() == path.resolve():
            print("csvround: refusing to write over the input file", file=sys.stderr)
            return 2
        raw = path.read_text(encoding="utf-8-sig")

    reader = csv.reader(io.StringIO(raw), delimiter=args.delimiter)
    rows = []
    start = 1  # report the line each row starts on, like csvnum/csvcheck
    for row in reader:
        if row:
            rows.append((start, row))
        start = reader.line_num + 1
    if not rows:
        print("csvround: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0][1]]
    try:
        columns = pick_columns(args.columns, header)
    except ColumnError as e:
        print(f"csvround: {e}", file=sys.stderr)
        return 2

    body, bad = round_rows(rows[1:], columns, args.places, args.mode)
    for line, i, cell in bad:
        print(f"csvround: line {line}, {header[i]}: not a plain number {cell!r}", file=sys.stderr)
    if bad and args.strict:
        print(f"csvround: {len(bad)} non-numeric cell{'s' if len(bad) != 1 else ''}, nothing written",
              file=sys.stderr)
        return 1

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(body)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""csvtranspose - swap the rows and columns of a CSV.

Row i, column j becomes row j, column i, so a sideways report (one column per
month, one row per metric) becomes one row per month, and a one-row settings
export becomes an easy-to-read `name,value` list. Short rows are padded with
empty cells first so no value moves to the wrong place; trailing empty
columns that only came from that padding are dropped from the result unless
`--keep-trailing`. The whole file is held in memory, so `--max-cells` (default
5 million) refuses unexpectedly huge inputs instead of filling RAM.

    python -m minitools.csvtranspose report.csv -o by_month.csv
    python -m minitools.csvtranspose settings.csv -d ';' --out-delimiter ,
    python -m minitools.csvtranspose - < wide.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path


def transpose(rows: list[list[str]], keep_trailing: bool = False) -> list[list[str]]:
    """Transpose a ragged list of rows; short rows are padded with "" first.

    Without ``keep_trailing``, output rows lose trailing cells that are empty,
    so padding added for short input rows does not show up as dangling commas.
    Rows that end up completely empty are kept as [] only if they are not at the end.
    """
    rows = [r for r in rows if r]  # csv gives [] for blank lines
    if not rows:
        return []
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    out = [list(col) for col in zip(*padded)]
    if not keep_trailing:
        for r in out:
            while r and r[-1] == "":
                r.pop()
        while out and not out[-1]:
            out.pop()
    return out


def _delimiter(value: str) -> str:
    value = "\t" if value in ("\\t", "tab") else value
    if len(value) != 1:
        raise argparse.ArgumentTypeError("delimiter must be a single character (or \\t)")
    return value


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-d", "--delimiter", type=_delimiter, default=",", help="input delimiter (default ',', \\t for tab)")
    p.add_argument("--out-delimiter", type=_delimiter, help="output delimiter (default: same as input)")
    p.add_argument("--keep-trailing", action="store_true", help="keep trailing empty cells in the output rows")
    p.add_argument("--max-cells", type=int, default=5_000_000, help="refuse inputs with more cells (default 5000000)")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)
    if args.max_cells < 1:
        p.error("--max-cells must be >= 1")

    if args.input == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvtranspose: no such file: {path}", file=sys.stderr)
            return 1
        if args.output and args.output.resolve() == path.resolve():
            print("csvtranspose: refusing to write over the input file", file=sys.stderr)
            return 2
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            print(f"csvtranspose: {path} is not valid UTF-8 (byte 0x{exc.object[exc.start]:02x} "
                  f"at offset {exc.start})", file=sys.stderr)
            return 1

    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=args.delimiter))
    cells = sum(len(r) for r in rows)
    if cells > args.max_cells:
        print(f"csvtranspose: {cells} cells is more than --max-cells {args.max_cells}", file=sys.stderr)
        return 2

    buf = io.StringIO()
    csv.writer(buf, delimiter=args.out_delimiter or args.delimiter, lineterminator="\n").writerows(
        transpose(rows, args.keep_trailing)
    )
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8", newline="")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

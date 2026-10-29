"""csvnum - rewrite number columns in a CSV as plain machine-readable decimals.

Exports from spreadsheets and banks write the same amount in many ways:
"1.234,50", "1,234.50", "€ 1 234,50", "(12.00)", "12.00-", "1'234.5". This
turns the chosen columns into one form ("1234.50", "-12.00") that every tool
and database reads, keeping the decimals that were written.

    python -m minitools.csvnum bank.csv -c amount,balance --decimal comma -d ";" -o clean.csv
    python -m minitools.csvnum sales.csv -c price --strict

`--decimal dot|comma` says which mark is the decimal point; the default
`auto` decides per cell: with both marks the last one is the decimal point,
a mark used more than once is a thousands separator, and "1,234" (one mark
followed by exactly three digits) is ambiguous and reported instead of
guessed. Thousands groups must be three digits, so "12.34.5" is rejected.
Spaces (including non-breaking ones), apostrophes, currency signs and the
codes EUR/USD/GBP/CHF are dropped; "(12)" and a trailing minus mean negative.

Cells that cannot be read are left unchanged and listed on stderr with their
line number; `--strict` makes that an error (exit 1, nothing written). Empty
cells stay empty. Reads a file or stdin ("-"), writes stdout or -o.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

CURRENCY = re.compile(r"^(?:EUR|USD|GBP|CHF)|(?:EUR|USD|GBP|CHF)$|[€$£¥]", re.IGNORECASE)
SPACES = re.compile(r"[\s'’]")
GROUPED = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")
SPACED = re.compile(r"\d{1,3}(?:[\s'’]\d{3})+(?:[.,]\d+)?")


class ColumnError(ValueError):
    pass


def parse_number(text: str, decimal: str = "auto") -> Decimal | None:
    """Read one formatted number; None when it cannot be read unambiguously."""
    s = CURRENCY.sub("", text.strip()).strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1].strip()
    if s.endswith("-") and not s.startswith(("-", "+")):
        negative, s = True, s[:-1]
    if s[:1] in "+-" and s:
        negative, s = negative or s[0] == "-", s[1:]
    s = CURRENCY.sub("", s.strip()).strip()
    spaced = bool(SPACES.search(s))
    if spaced:
        # space/apostrophe thousands: "1 234", "1'234.5"; any mark left is the decimal point
        if not SPACED.fullmatch(s):
            return None
        s = SPACES.sub("", s)
    if not re.fullmatch(r"[\d.,]+", s) or not any(ch.isdigit() for ch in s):
        return None

    mark = decimal_mark(s, decimal, spaced)
    if mark is False:
        return None
    if mark:
        whole, _, frac = s.rpartition(mark)
        if not frac.isdigit():
            return None
    else:
        whole, frac = s, ""
    if any(sep in whole for sep in ".,"):
        if not GROUPED.match(whole) or len(set(re.sub(r"\d", "", whole))) != 1:
            return None
        whole = re.sub(r"[.,]", "", whole)
    if not whole.isdigit():
        if whole or not frac:
            return None
        whole = "0"  # ".5"
    try:
        value = Decimal(f"{whole}.{frac}" if frac else whole)
    except InvalidOperation:
        return None
    return -value if negative and value else value


def decimal_mark(s: str, decimal: str, spaced: bool = False) -> str | None | bool:
    """The decimal mark in ``s`` ("." / ","), None for an integer, False if ambiguous/invalid.

    ``spaced`` means the thousands were already split by spaces/apostrophes, so
    a single remaining mark can only be the decimal point.
    """
    if decimal in ("dot", "comma"):
        mark, other = (".", ",") if decimal == "dot" else (",", ".")
        if s.count(mark) > 1:
            return False
        if mark in s:
            return mark
        return None if other not in s or GROUPED.match(s) else False
    has_dot, has_comma = "." in s, "," in s
    if spaced:
        if has_dot and has_comma:
            return False
        return "." if has_dot else "," if has_comma else None
    if has_dot and has_comma:
        return "." if s.rfind(".") > s.rfind(",") else ","
    mark = "." if has_dot else "," if has_comma else None
    if mark is None:
        return None
    if s.count(mark) > 1:
        return None if GROUPED.match(s) else False  # repeated mark: thousands only
    after = len(s) - s.index(mark) - 1
    if after == 3 and s.index(mark) > 0:
        return False  # "1,234": thousands or decimal? refuse to guess
    return mark


def format_number(value: Decimal) -> str:
    text = format(value, "f")
    return text[1:] if text.startswith("-") and value == 0 else text


def pick_columns(names: list[str], header: list[str]) -> list[int]:
    wanted = [n.strip() for part in names for n in part.split(",") if n.strip()]
    unknown = [n for n in wanted if n not in header]
    if unknown:
        raise ColumnError(f"unknown column(s): {', '.join(unknown)}; available: {', '.join(header)}")
    return sorted({header.index(n) for n in wanted})


def normalise_rows(
    rows: list[tuple[int, list[str]]], columns: list[int], decimal: str = "auto"
) -> tuple[list[list[str]], list[tuple[int, int, str]]]:
    """Return (new rows, [(line, column index, cell) that could not be read])."""
    out, bad = [], []
    for line, row in rows:
        new = list(row)
        for i in columns:
            if i >= len(new) or not new[i].strip():
                continue
            value = parse_number(new[i], decimal)
            if value is None:
                bad.append((line, i, new[i]))
            else:
                new[i] = format_number(value)
        out.append(new)
    return out, bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--columns", action="append", required=True, metavar="NAMES",
                   help="comma-separated number columns; repeatable")
    p.add_argument("--decimal", choices=["auto", "dot", "comma"], default="auto",
                   help="decimal mark in the input (default: auto per cell)")
    p.add_argument("--strict", action="store_true", help="fail (exit 1) if any cell cannot be read")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvnum: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    reader = csv.reader(io.StringIO(raw), delimiter=args.delimiter)
    rows = []
    start = 1  # report the line each row starts on, like csvcheck/csvgroup
    for row in reader:
        if row:
            rows.append((start, row))
        start = reader.line_num + 1
    if not rows:
        print("csvnum: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0][1]]
    try:
        columns = pick_columns(args.columns, header)
    except ColumnError as e:
        print(f"csvnum: {e}", file=sys.stderr)
        return 2

    body, bad = normalise_rows(rows[1:], columns, args.decimal)
    for line, i, cell in bad:
        print(f"csvnum: line {line}, {header[i]}: cannot read {cell!r}", file=sys.stderr)
    if bad and args.strict:
        print(f"csvnum: {len(bad)} unreadable cell{'s' if len(bad) != 1 else ''}, nothing written", file=sys.stderr)
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

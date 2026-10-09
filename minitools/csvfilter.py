"""csvfilter - keep only the CSV rows that match column conditions.

Each `-w` condition is "column OP value" with OP one of
  =  !=            equal / not equal (numbers compare as numbers, so 5 = 5.0)
  >  >=  <  <=     numeric comparison; cells that are not numbers never match
  ~  !~            regular-expression search / no match
Several `-w` are combined with AND, or with OR under `--any`. `-i` makes
=, != and the regex operators case-insensitive. Unknown columns are an error
that lists the real headers. Reads a file or stdin ("-"), writes stdout or -o;
`--count` prints only the number of matching rows.

    python -m minitools.csvfilter sales.csv -w "country=NL" -w "amount>=100" [-o out.csv]
    python -m minitools.csvfilter users.csv -w "email~@example\\.com$" --count
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_COND = re.compile(r"^\s*(.+?)\s*(!=|>=|<=|!~|=|>|<|~)\s*(.*?)\s*$")
_NUMERIC_OPS = {">", ">=", "<", "<="}


class ConditionError(ValueError):
    pass


def _number(text: str) -> float | None:
    try:
        value = float(text.strip())
    except ValueError:
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


@dataclass
class Condition:
    column: str
    op: str
    value: str
    ignore_case: bool = False

    def __post_init__(self):
        self._num = _number(self.value)
        if self.op in _NUMERIC_OPS and self._num is None:
            raise ConditionError(f"{self.op} needs a number, got {self.value!r}")
        self._regex = None
        if self.op in ("~", "!~"):
            try:
                self._regex = re.compile(self.value, re.IGNORECASE if self.ignore_case else 0)
            except re.error as e:
                raise ConditionError(f"bad regex {self.value!r}: {e}") from None

    def matches(self, cell: str) -> bool:
        cell = cell.strip()
        if self._regex is not None:
            found = self._regex.search(cell) is not None
            return found if self.op == "~" else not found
        num = _number(cell)
        if self.op in _NUMERIC_OPS:
            if num is None:
                return False
            return {">": num > self._num, ">=": num >= self._num,
                    "<": num < self._num, "<=": num <= self._num}[self.op]
        if num is not None and self._num is not None:
            equal = num == self._num
        elif self.ignore_case:
            equal = cell.casefold() == self.value.casefold()
        else:
            equal = cell == self.value
        return equal if self.op == "=" else not equal


def parse_condition(text: str, ignore_case: bool = False) -> Condition:
    m = _COND.match(text)
    if not m:
        raise ConditionError(f"cannot parse condition {text!r}; expected e.g. 'amount>=100'")
    return Condition(m.group(1), m.group(2), m.group(3), ignore_case)


def filter_rows(
    header: list[str], rows: list[list[str]], conditions: list[Condition], any_match: bool = False
) -> list[list[str]]:
    """Rows that satisfy all conditions (or at least one with ``any_match``).

    Short rows are treated as having empty cells. Raises ConditionError for
    columns that are not in the header.
    """
    missing = [c.column for c in conditions if c.column not in header]
    if missing:
        raise ConditionError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    idx = [header.index(c.column) for c in conditions]
    combine = any if any_match else all
    out = []
    for row in rows:
        cells = [row[i] if i < len(row) else "" for i in idx]
        if not conditions or combine(c.matches(cell) for c, cell in zip(conditions, cells)):
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-w", "--where", action="append", required=True, help='condition like "amount>=100" (repeatable)')
    p.add_argument("--any", action="store_true", help="keep rows matching at least one condition (default: all)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="case-insensitive =, != and regex")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    p.add_argument("--count", action="store_true", help="print only the number of matching rows")
    args = p.parse_args(argv)

    try:
        conditions = [parse_condition(w, args.ignore_case) for w in args.where]
    except ConditionError as e:
        print(f"csvfilter: {e}", file=sys.stderr)
        return 2

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvfilter: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvfilter: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        kept = filter_rows(header, rows[1:], conditions, any_match=args.any)
    except ConditionError as e:
        print(f"csvfilter: {e}", file=sys.stderr)
        return 2

    if args.count:
        print(len(kept))
        return 0
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=args.delimiter, lineterminator="\n")
    writer.writerow(rows[0])
    writer.writerows(kept)
    if args.output:
        args.output.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

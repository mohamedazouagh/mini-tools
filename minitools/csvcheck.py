"""csvcheck - validate CSV columns against simple rules before loading the data.

Each `-r column:rule` (repeatable) checks every row; a column can have
several rules (`-r id:required -r id:unique`). Rules:

    required   cell must not be empty
    int        whole number (an optional leading sign), e.g. 42, -7
    number     int or decimal, e.g. 3.5, -0.25, 1e3 (not nan/inf, not 1_000)
    date       ISO date YYYY-MM-DD that exists on the calendar
    email      something@domain.tld (a sanity check, not full RFC 5322)
    unique     no value repeated in the column (empty cells ignored)

Cells are trimmed, and empty cells only fail `required`, so optional
columns can still be type-checked. Problems are listed with their file line
number. Exit 0 valid / 1 problems found / 2 bad input or unknown column.

    python -m minitools.csvcheck orders.csv -r id:required -r id:unique -r amount:number
    python -m minitools.csvcheck - -r date:date -d ';' --max-errors 20 < export.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import re
import sys
from datetime import date
from pathlib import Path

INT_RE = re.compile(r"[+-]?\d+")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_number(v: str) -> bool:
    if "_" in v:
        return False
    try:
        return math.isfinite(float(v))
    except ValueError:
        return False


def _is_date(v: str) -> bool:
    if not DATE_RE.fullmatch(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


TYPE_CHECKS = {
    "int": lambda v: INT_RE.fullmatch(v) is not None,
    "number": _is_number,
    "date": _is_date,
    "email": lambda v: EMAIL_RE.fullmatch(v) is not None,
}
RULES = ("required", "unique", *TYPE_CHECKS)
MESSAGES = {"int": "not a whole number", "number": "not a number", "date": "not a valid YYYY-MM-DD date",
            "email": "not an email address"}


def parse_rule(spec: str) -> tuple[str, str]:
    col, sep, rule = spec.rpartition(":")
    col, rule = col.strip(), rule.strip().lower()
    if not sep or not col:
        raise ValueError(f"bad rule {spec!r}: use column:rule")
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r} in {spec!r}; choose from {', '.join(RULES)}")
    return col, rule


def check_rows(
    header: list[str], rows: list[tuple[int, list[str]]], rules: list[tuple[str, str]]
) -> list[tuple[int, str, str]]:
    """Return problems as (line number, column, message), in file order.

    ``rows`` pairs each data row with its line number in the file. Raises
    ValueError for a rule on a column that is not in the header.
    """
    missing = sorted({c for c, _ in rules if c not in header})
    if missing:
        raise ValueError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    problems: list[tuple[int, str, str]] = []
    seen: dict[str, dict[str, int]] = {c: {} for c, r in rules if r == "unique"}
    for line, row in rows:
        for col, rule in rules:
            i = header.index(col)
            v = row[i].strip() if i < len(row) else ""
            if rule == "required":
                if not v:
                    problems.append((line, col, "empty"))
            elif not v:
                continue
            elif rule == "unique":
                first = seen[col].setdefault(v, line)
                if first != line:
                    problems.append((line, col, f"{v!r} already used on line {first}"))
            elif not TYPE_CHECKS[rule](v):
                problems.append((line, col, f"{v!r} is {MESSAGES[rule]}"))
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-r", "--rule", action="append", required=True, metavar="COLUMN:RULE",
                   help=f"rule to check (repeatable): {', '.join(RULES)}")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("--max-errors", type=int, default=50, help="list at most N problems (0 = all, default 50)")
    args = p.parse_args(argv)
    if args.max_errors < 0:
        p.error("--max-errors must be >= 0")
    try:
        rules = [parse_rule(s) for s in args.rule]
    except ValueError as e:
        p.error(str(e))

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvcheck: no such file: {path}", file=sys.stderr)
            return 2
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as e:
            print(f"csvcheck: {path} is not valid UTF-8 ({e.reason} at byte {e.start})", file=sys.stderr)
            return 2

    reader = csv.reader(io.StringIO(raw), delimiter=args.delimiter)
    numbered: list[tuple[int, list[str]]] = []
    prev_end = 0
    for r in reader:  # a quoted cell can span lines: report the line the row starts on
        if any(c.strip() for c in r):
            numbered.append((prev_end + 1, r))
        prev_end = reader.line_num
    if not numbered:
        print("csvcheck: input has no header row", file=sys.stderr)
        return 2
    header = [h.strip() for h in numbered[0][1]]
    try:
        problems = check_rows(header, numbered[1:], rules)
    except ValueError as e:
        print(f"csvcheck: {e}", file=sys.stderr)
        return 2

    n_rows = len(numbered) - 1
    shown = problems if not args.max_errors else problems[: args.max_errors]
    for line, col, msg in shown:
        print(f"line {line}: {col}: {msg}")
    if len(shown) < len(problems):
        print(f"... and {len(problems) - len(shown)} more")
    if problems:
        bad_rows = len({line for line, _, _ in problems})
        print(f"{len(problems)} problem(s) in {bad_rows} of {n_rows} row(s)", file=sys.stderr)
        return 1
    print(f"ok: {n_rows} row(s) passed {len(rules)} rule(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""csvgroup - group CSV rows by one or more columns and aggregate others.

A small GROUP BY for CSV files: `-g country` (or `-g country,status`) picks
the group key, and each `-a` adds an output column: `count` (rows in the
group), `col:sum`, `col:mean`, `col:median`, `col:min`, `col:max` (numeric)
or `col:distinct` (number of different non-empty values). The median is
exact and is not affected by a few huge values the way the mean is, which
suits skewed columns like order amounts. Without `-a` only the
row count is shown. Numbers are added up with `decimal`, so money columns
like 0.10 + 0.20 come out as 0.30, not 0.30000000000000004. Cells are
trimmed; empty cells are skipped by the numeric aggregates (a group without
any numbers shows an empty cell) and an empty group key is shown as
"(blank)". A cell that is not a number fails with its line number instead of
being silently ignored. Groups are listed by key: numbers numerically, text
case-insensitively, "(blank)" last.

    python -m minitools.csvgroup sales.csv -g country -a count -a amount:sum
    python -m minitools.csvgroup sales.csv -g country,status -a amount:mean --csv
    python -m minitools.csvgroup - -g city -a customer:distinct -d ';' < sales.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

BLANK = "(blank)"
NUMERIC = ("sum", "mean", "median", "min", "max")
FUNCS = (*NUMERIC, "distinct")


class GroupError(ValueError):
    pass


@dataclass(frozen=True)
class Agg:
    func: str
    column: str | None = None

    @property
    def label(self) -> str:
        return "count" if self.func == "count" else f"{self.column}_{self.func}"


def parse_agg(spec: str) -> Agg:
    """Turn "count" or "column:func" into an Agg."""
    spec = spec.strip()
    if spec == "count":
        return Agg("count")
    col, sep, func = spec.rpartition(":")
    col, func = col.strip(), func.strip().lower()
    if not sep or not col or func not in FUNCS:
        raise GroupError(f"bad aggregate {spec!r}; use count or column:{'|'.join(FUNCS)}")
    return Agg(func, col)


def _number(cell: str, column: str, line: int) -> Decimal:
    try:
        value = Decimal(cell)
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite() or "_" in cell:
        raise GroupError(f"line {line}: {cell!r} in column {column!r} is not a number")
    return value


@dataclass
class _Group:
    rows: int = 0
    numbers: dict[str, list[Decimal]] = field(default_factory=dict)
    values: dict[str, set[str]] = field(default_factory=dict)


def group_rows(
    header: list[str], rows: list[tuple[int, list[str]]], keys: list[str], aggs: list[Agg]
) -> dict[tuple[str, ...], _Group]:
    """Collect the values each aggregate needs, per group key.

    ``rows`` are (line number, cells) pairs; the line number is only used in
    error messages. Short rows count as empty cells.
    """
    unknown = [c for c in [*keys, *(a.column for a in aggs if a.column)] if c not in header]
    if unknown:
        raise GroupError(f"unknown column(s): {', '.join(dict.fromkeys(unknown))}; available: {', '.join(header)}")
    key_idx = [header.index(k) for k in keys]
    # each column is collected once, however many aggregates use it
    numeric_cols = list(dict.fromkeys(a.column for a in aggs if a.func in NUMERIC))
    distinct_cols = list(dict.fromkeys(a.column for a in aggs if a.func == "distinct"))
    groups: dict[tuple[str, ...], _Group] = {}
    for line, row in rows:
        cells = [c.strip() for c in row] + [""] * (len(header) - len(row))
        key = tuple(cells[i] or BLANK for i in key_idx)
        g = groups.setdefault(key, _Group())
        g.rows += 1
        for col in numeric_cols:
            cell = cells[header.index(col)]
            if cell:
                g.numbers.setdefault(col, []).append(_number(cell, col, line))
        for col in distinct_cols:
            cell = cells[header.index(col)]
            if cell:
                g.values.setdefault(col, set()).add(cell)
    return groups


def _fmt(d: Decimal) -> str:
    text = format(d, "f")
    return "0" if text in ("-0", "") else text


def aggregate(g: _Group, agg: Agg, precision: int = 2) -> str:
    if agg.func == "count":
        return str(g.rows)
    if agg.func == "distinct":
        return str(len(g.values.get(agg.column, ())))
    nums = g.numbers.get(agg.column)
    if not nums:
        return ""
    if agg.func == "sum":
        return _fmt(sum(nums, Decimal(0)))
    if agg.func == "min":
        return _fmt(min(nums))
    if agg.func == "max":
        return _fmt(max(nums))
    if agg.func == "median":
        # exact: the middle value, or the average of the two middle ones (halving a
        # Decimal never needs rounding), so 0.10 and 0.25 give 0.175, not 0.17
        ordered = sorted(nums)
        mid = len(ordered) // 2
        median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
        return _fmt(median)
    mean = sum(nums, Decimal(0)) / len(nums)
    return _fmt(mean.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP))


def _key_part(v: str) -> tuple:
    if v == BLANK:
        return (2, Decimal(0), "")
    try:
        num = Decimal(v)
    except InvalidOperation:
        num = None
    if num is not None and num.is_finite() and "_" not in v:
        return (0, num, v)
    return (1, Decimal(0), v.casefold())


def build_table(
    header: list[str], rows: list[tuple[int, list[str]]], keys: list[str], aggs: list[Agg], precision: int = 2
) -> list[list[str]]:
    """Header row plus one row per group, sorted by key."""
    groups = group_rows(header, rows, keys, aggs)
    ordered = sorted(groups.items(), key=lambda kv: tuple(_key_part(v) for v in kv[0]))
    out = [[*keys, *(a.label for a in aggs)]]
    out += [[*key, *(aggregate(g, a, precision) for a in aggs)] for key, g in ordered]
    return out


def format_table(table: list[list[str]], n_keys: int) -> str:
    widths = [max(len(r[i]) for r in table) for i in range(len(table[0]))]

    def line(cells: list[str]) -> str:
        return "  ".join(c.ljust(w) if i < n_keys else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths))).rstrip()

    return "\n".join(line(r) for r in table) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-g", "--group", required=True, help="column, or comma-separated columns, to group by")
    p.add_argument(
        "-a", "--agg", action="append", default=[],
        help="count or column:sum|mean|median|min|max|distinct (repeatable; default count)",
    )
    p.add_argument("--precision", type=int, default=2, help="decimals for mean (default 2)")
    p.add_argument("--csv", action="store_true", help="write CSV instead of an aligned table")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    args = p.parse_args(argv)
    if args.precision < 0:
        p.error("--precision must be >= 0")
    try:
        aggs = [parse_agg(s) for s in args.agg] or [Agg("count")]
    except GroupError as e:
        p.error(str(e))
    keys = [k.strip() for k in args.group.split(",") if k.strip()]
    if not keys:
        p.error("--group needs at least one column name")

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvgroup: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    reader = csv.reader(io.StringIO(raw), delimiter=args.delimiter)
    rows: list[tuple[int, list[str]]] = []
    start = 1
    for row in reader:
        if any(c.strip() for c in row):
            rows.append((start, row))
        start = reader.line_num + 1
    if not rows:
        print("csvgroup: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0][1]]
    try:
        table = build_table(header, rows[1:], keys, aggs, args.precision)
    except GroupError as e:
        print(f"csvgroup: {e}", file=sys.stderr)
        return 2

    if args.csv:
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows(table)
        sys.stdout.write(buf.getvalue())
    else:
        sys.stdout.write(format_table(table, len(keys)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

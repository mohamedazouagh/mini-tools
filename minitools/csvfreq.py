"""csvfreq - frequency table of the values in one or more CSV columns.

The CSV version of `cut | sort | uniq -c | sort -rn`: counts each distinct
value of a column (or a combination of columns with `-c a,b`), most common
first, with its share of the counted rows. Cells are trimmed; empty cells are
counted as "(blank)" so missing data stays visible, or left out (and out of
the shares) with `--no-blank`.
`-i` merges values that differ only in case (the most common spelling is
shown). Reads a file or stdin ("-"), prints an aligned table or `--csv`.

    python -m minitools.csvfreq orders.csv -c country
    python -m minitools.csvfreq orders.csv -c country,status -n 5 -d ';'
    python -m minitools.csvfreq - -c city -i --no-blank --csv < orders.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter
from pathlib import Path

BLANK = "(blank)"


class ColumnError(ValueError):
    pass


def column_indexes(header: list[str], names: list[str]) -> list[int]:
    missing = [n for n in names if n not in header]
    if missing:
        raise ColumnError(f"unknown column(s): {', '.join(missing)}; available: {', '.join(header)}")
    return [header.index(n) for n in names]


def count_values(
    rows: list[list[str]], idx: list[int], ignore_case: bool = False, keep_blank: bool = True
) -> list[tuple[tuple[str, ...], int]]:
    """Count value tuples for the columns in ``idx``, most common first.

    Ties are ordered by value so the output is stable. Short rows count as
    blank cells. A key is blank when every selected cell is empty; with
    ``keep_blank=False`` those rows are skipped. With ``ignore_case`` the
    shown spelling of a merged key is its most frequent one (first seen wins
    ties).
    """
    counts: Counter[tuple[str, ...]] = Counter()
    spellings: dict[tuple[str, ...], Counter[tuple[str, ...]]] = {}
    for row in rows:
        key = tuple(row[i].strip() if i < len(row) else "" for i in idx)
        if not any(key) and not keep_blank:
            continue
        key = tuple(v or BLANK for v in key)
        norm = tuple(v.casefold() for v in key) if ignore_case else key
        counts[norm] += 1
        spellings.setdefault(norm, Counter())[key] += 1
    shown = [(spellings[k].most_common(1)[0][0], n) for k, n in counts.items()]
    return sorted(shown, key=lambda kv: (-kv[1], kv[0]))


def format_table(names: list[str], counted: list[tuple[tuple[str, ...], int]], total: int) -> str:
    header = [*names, "count", "share"]
    body = [[*key, str(n), f"{n / total * 100:.1f}%"] for key, n in counted]
    widths = [max(len(r[i]) for r in [header, *body]) for i in range(len(header))]
    n_text = len(names)

    def line(cells: list[str]) -> str:
        return "  ".join(c.ljust(w) if i < n_text else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths))).rstrip()

    return "\n".join([line(header), *(line(r) for r in body)]) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--columns", required=True, help="column, or comma-separated columns to count together")
    p.add_argument("-n", "--top", type=int, default=0, help="show only the N most common values (default all)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="merge values that differ only in case")
    p.add_argument("--no-blank", action="store_true", help="skip rows where the column(s) are empty")
    p.add_argument("--csv", action="store_true", help="write CSV instead of an aligned table")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    args = p.parse_args(argv)
    if args.top < 0:
        p.error("--top must be >= 0")

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvfreq: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if any(c.strip() for c in r)]
    if not rows:
        print("csvfreq: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    names = [n.strip() for n in args.columns.split(",") if n.strip()]
    try:
        idx = column_indexes(header, names)
    except ColumnError as e:
        print(f"csvfreq: {e}", file=sys.stderr)
        return 2

    counted = count_values(rows[1:], idx, ignore_case=args.ignore_case, keep_blank=not args.no_blank)
    total = sum(n for _, n in counted)
    if not total:
        print("csvfreq: no values to count", file=sys.stderr)
        return 1
    if args.top:
        counted = counted[: args.top]

    if args.csv:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow([*names, "count", "share"])
        w.writerows([*key, n, f"{n / total * 100:.1f}"] for key, n in counted)
        sys.stdout.write(buf.getvalue())
    else:
        sys.stdout.write(format_table(names, counted, total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

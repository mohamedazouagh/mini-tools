"""csvdiff - compare two versions of a CSV by a key column.

Rows are matched on the key (-k), not on their position, so reordering a file
is not a change. Prints one line per added (+), removed (-) and changed (~)
key, with the cells that changed, then a summary. Columns present in only one
file are reported and left out of the cell comparison. Cells are compared
after trimming spaces. Exit code: 0 identical, 1 differences, 2 bad input
(like diff).

    python -m minitools.csvdiff old.csv new.csv -k id [-d ';'] [--summary]
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path


class DiffError(ValueError):
    pass


@dataclass
class Diff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)
    unchanged: int = 0
    columns_added: list[str] = field(default_factory=list)
    columns_removed: list[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return not (self.added or self.removed or self.changed or self.columns_added or self.columns_removed)


def _index(rows: list[list[str]], key: str, label: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Header and {key: {column: cell}} for one file. Duplicate or missing keys are errors."""
    if not rows:
        raise DiffError(f"{label} has no header row")
    header = [h.strip() for h in rows[0]]
    if key not in header:
        raise DiffError(f"key column {key!r} not in {label}; available: {', '.join(header)}")
    by_key: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        record = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(header)}
        k = record[key]
        if k in by_key:
            raise DiffError(f"duplicate key {k!r} in {label}")
        by_key[k] = record
    return header, by_key


def diff_rows(old: list[list[str]], new: list[list[str]], key: str) -> Diff:
    old_header, old_rows = _index(old, key, "old file")
    new_header, new_rows = _index(new, key, "new file")
    shared = [h for h in old_header if h in new_header and h != key]
    d = Diff(
        columns_added=[h for h in new_header if h not in old_header],
        columns_removed=[h for h in old_header if h not in new_header],
    )
    d.removed = [k for k in old_rows if k not in new_rows]
    d.added = [k for k in new_rows if k not in old_rows]
    for k, before in old_rows.items():
        after = new_rows.get(k)
        if after is None:
            continue
        cells = [(c, before[c], after[c]) for c in shared if before[c] != after[c]]
        if cells:
            d.changed[k] = cells
        else:
            d.unchanged += 1
    return d


def format_diff(d: Diff, summary_only: bool = False) -> str:
    lines = []
    if d.columns_added:
        lines.append(f"columns added: {', '.join(d.columns_added)}")
    if d.columns_removed:
        lines.append(f"columns removed: {', '.join(d.columns_removed)}")
    if not summary_only:
        lines += [f"- {k}" for k in d.removed]
        lines += [f"+ {k}" for k in d.added]
        for k, cells in d.changed.items():
            parts = "; ".join(f"{c}: {a!r} -> {b!r}" for c, a, b in cells)
            lines.append(f"~ {k}: {parts}")
    lines.append(
        f"added {len(d.added)}, removed {len(d.removed)}, changed {len(d.changed)}, unchanged {d.unchanged}"
    )
    return "\n".join(lines) + "\n"


def _read(path: Path, delimiter: str) -> list[list[str]]:
    raw = path.read_text(encoding="utf-8-sig")
    return [r for r in csv.reader(io.StringIO(raw), delimiter=delimiter) if r]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("old", type=Path, help="earlier version of the CSV")
    p.add_argument("new", type=Path, help="later version of the CSV")
    p.add_argument("-k", "--key", required=True, help="column that identifies a row")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("--summary", action="store_true", help="only print the counts")
    args = p.parse_args(argv)

    for path in (args.old, args.new):
        if not path.is_file():
            print(f"csvdiff: no such file: {path}", file=sys.stderr)
            return 2
    try:
        d = diff_rows(_read(args.old, args.delimiter), _read(args.new, args.delimiter), args.key.strip())
    except DiffError as e:
        print(f"csvdiff: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(format_diff(d, summary_only=args.summary))
    return 0 if d.identical else 1


if __name__ == "__main__":
    raise SystemExit(main())

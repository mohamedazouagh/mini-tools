"""csvmask - pseudonymise or mask sensitive CSV columns before sharing a file.

`-c COLUMN[:MODE]` (repeatable) picks a column and what to do with it:

- `hash` (default): replace the cell with a short HMAC-SHA256 token. The same
  input always gives the same token, so joins, counts and dedupes still work on
  the masked file, but the original value is not in it. Pass `--salt` (or set
  the CSVMASK_SALT environment variable) with a secret; without one, common
  values such as e-mail addresses can be recovered by hashing guesses, so a
  warning is printed.
- `mask`: keep only the last `--keep` characters (default 4) and replace the
  rest with `*`, e.g. a phone number `0612345678` -> `******5678`. Cells not
  longer than `--keep` are masked completely.
- `blank`: empty the cell.

Cells are trimmed first; empty cells stay empty. `-i` lowercases before
hashing so `Ana@Example.com` and `ana@example.com` get the same token.

    python -m minitools.csvmask customers.csv -c email -c phone:mask --salt "$SECRET" -o share.csv
    python -m minitools.csvmask export.csv -c name:blank -c iban:mask --keep 4 -d ';'

Reads a file or stdin ("-"), writes stdout or -o. Unknown column names list the
real headers (exit 2).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import os
import sys
from pathlib import Path

MODES = ("hash", "mask", "blank")
TOKEN_LEN = 12


class ColumnError(ValueError):
    pass


def parse_specs(specs: list[str], header: list[str]) -> list[tuple[int, str]]:
    """Turn ["email", "phone:mask"] into [(index, mode), ...]."""
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for spec in specs:
        name, _, mode = spec.partition(":")
        name, mode = name.strip(), (mode.strip() or "hash")
        if mode not in MODES:
            raise ColumnError(f"unknown mode '{mode}' for {name}; use one of: {', '.join(MODES)}")
        if name not in header:
            raise ColumnError(f"unknown column(s): {name}; available: {', '.join(header)}")
        i = header.index(name)
        if i in seen:
            raise ColumnError(f"column {name} given more than once")
        seen.add(i)
        out.append((i, mode))
    return out


def hash_token(value: str, salt: str, ignore_case: bool = False) -> str:
    v = value.strip()
    if not v:
        return ""
    if ignore_case:
        v = v.casefold()
    return hmac.new(salt.encode("utf-8"), v.encode("utf-8"), hashlib.sha256).hexdigest()[:TOKEN_LEN]


def mask_value(value: str, keep: int = 4) -> str:
    v = value.strip()
    if len(v) <= keep:
        return "*" * len(v)
    return "*" * (len(v) - keep) + (v[-keep:] if keep else "")


def mask_rows(
    rows: list[list[str]], specs: list[tuple[int, str]], salt: str = "", keep: int = 4, ignore_case: bool = False
) -> list[list[str]]:
    """Apply each (column index, mode) to every row; short rows are left short."""
    out = []
    for row in rows:
        new = list(row)
        for i, mode in specs:
            if i >= len(new):
                continue
            if mode == "hash":
                new[i] = hash_token(new[i], salt, ignore_case)
            elif mode == "mask":
                new[i] = mask_value(new[i], keep)
            else:
                new[i] = ""
        out.append(new)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-c", "--column", action="append", required=True, metavar="NAME[:MODE]",
                   help="column to protect, mode hash (default), mask or blank; repeatable")
    p.add_argument("--salt", help="secret for hash mode (default: $CSVMASK_SALT)")
    p.add_argument("--keep", type=int, default=4, help="characters left visible in mask mode (default 4)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="lowercase values before hashing")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default ',')")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)

    if args.keep < 0:
        print("csvmask: --keep must be 0 or more", file=sys.stderr)
        return 2
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvmask: no such file: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8-sig")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=args.delimiter) if r]
    if not rows:
        print("csvmask: input has no header row", file=sys.stderr)
        return 1
    header = [h.strip() for h in rows[0]]
    try:
        specs = parse_specs(args.column, header)
    except ColumnError as e:
        print(f"csvmask: {e}", file=sys.stderr)
        return 2
    salt = args.salt if args.salt is not None else os.environ.get("CSVMASK_SALT", "")
    if not salt and any(mode == "hash" for _, mode in specs):
        print("csvmask: warning: hashing without --salt; guessable values can be recovered", file=sys.stderr)

    body = mask_rows(rows[1:], specs, salt, args.keep, args.ignore_case)
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

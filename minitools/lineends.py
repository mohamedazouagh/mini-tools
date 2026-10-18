"""lineends - report and fix line endings (LF / CRLF / CR / mixed) and UTF-8 BOMs.

Without options it prints one line per file: the line-ending style, the
number of LF, CRLF and bare CR endings, whether the file starts with a
UTF-8 BOM and whether it ends with a newline. Folders are scanned
recursively (filter with `--glob`). Files containing NUL bytes are treated
as binary and skipped.

`--to lf` or `--to crlf` converts every ending to that style. It is a dry
run that lists the files that would change; add `--apply` to write them.
`--strip-bom` removes a UTF-8 BOM (also dry run unless `--apply`).
`--check lf|crlf` writes nothing and exits 1 when any file uses another
style (handy in CI).

    python -m minitools.lineends data --glob "*.csv"
    python -m minitools.lineends notes.txt export.csv --to lf --strip-bom --apply
    python -m minitools.lineends src --glob "*.py" --check lf

Exit codes: 0 ok, 1 --check found other styles, 2 bad input.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BOM = b"\xef\xbb\xbf"
_ENDING = re.compile(rb"\r\n|\r|\n")


@dataclass
class Report:
    lf: int
    crlf: int
    cr: int
    bom: bool
    final_newline: bool

    @property
    def style(self) -> str:
        kinds = [name for name, n in (("LF", self.lf), ("CRLF", self.crlf), ("CR", self.cr)) if n]
        if not kinds:
            return "none"
        return kinds[0] if len(kinds) == 1 else "mixed"


def inspect(data: bytes) -> Report:
    """Count each kind of line ending in ``data`` (a lone CR before LF is part of CRLF)."""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    cr = data.count(b"\r") - crlf
    return Report(lf=lf, crlf=crlf, cr=cr, bom=data.startswith(BOM), final_newline=data.endswith((b"\n", b"\r")))


def convert(data: bytes, to: str | None = None, strip_bom: bool = False) -> bytes:
    """Rewrite every line ending as ``to`` ("lf" or "crlf") and optionally drop a UTF-8 BOM."""
    if strip_bom and data.startswith(BOM):
        data = data[len(BOM):]
    if to is not None:
        if to not in ("lf", "crlf"):
            raise ValueError("to must be 'lf' or 'crlf'")
        data = _ENDING.sub(b"\n" if to == "lf" else b"\r\n", data)
    return data


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


def collect(paths: list[str], glob: str) -> tuple[list[Path], list[str]]:
    """Expand files and folders (recursively, matching ``glob``); returns (files, missing paths)."""
    files: list[Path] = []
    missing: list[str] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(f for f in p.rglob(glob) if f.is_file()))
        else:
            missing.append(raw)
    return files, missing


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("paths", nargs="+", help="files and/or folders")
    p.add_argument("--glob", default="*", help='pattern for files inside folders (default "*")')
    p.add_argument("--to", choices=["lf", "crlf"], help="convert line endings to this style")
    p.add_argument("--strip-bom", action="store_true", help="remove a UTF-8 byte-order mark")
    p.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    p.add_argument("--check", choices=["lf", "crlf"], help="exit 1 if any file uses another style")
    args = p.parse_args(argv)
    if args.check and (args.to or args.strip_bom or args.apply):
        p.error("--check cannot be combined with --to, --strip-bom or --apply")
    if args.apply and not (args.to or args.strip_bom):
        p.error("--apply needs --to and/or --strip-bom")

    files, missing = collect(args.paths, args.glob)
    for m in missing:
        print(f"lineends: no such file or folder: {m}", file=sys.stderr)
    if missing:
        return 2

    changing = args.to or args.strip_bom
    offenders = changed = 0
    for f in files:
        try:
            data = f.read_bytes()
        except OSError as e:
            print(f"lineends: skipped {f}: {e.strerror or e}", file=sys.stderr)
            continue
        if is_binary(data):
            print(f"lineends: skipped binary file {f}", file=sys.stderr)
            continue
        rep = inspect(data)
        if args.check:
            if rep.style not in ("none", args.check.upper()):
                offenders += 1
                print(f"{f}: {rep.style}")
            continue
        if changing:
            new = convert(data, args.to, args.strip_bom)
            if new == data:
                continue
            changed += 1
            if args.apply:
                f.write_bytes(new)
                print(f"fixed  {f}")
            else:
                print(f"would fix  {f} ({rep.style}{', BOM' if rep.bom else ''})")
            continue
        print(
            f"{rep.style:<5} lf={rep.lf} crlf={rep.crlf} cr={rep.cr}"
            f"  bom={'yes' if rep.bom else 'no'}  final-newline={'yes' if rep.final_newline else 'no'}  {f}"
        )

    if args.check:
        print(f"lineends: {offenders} file(s) not {args.check.upper()}", file=sys.stderr)
        return 1 if offenders else 0
    if changing:
        verb = "changed" if args.apply else "would change (use --apply)"
        print(f"lineends: {changed} file(s) {verb}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

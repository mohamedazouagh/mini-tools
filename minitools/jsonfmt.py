"""jsonfmt - validate and pretty-print (or compact) JSON and JSON Lines files.

Parses the input with the standard json module and writes it back with a
fixed layout: `--indent N` (default 2), or `--compact` for the smallest
output. `--sort-keys` gives a stable key order for diffs, non-ASCII text is
kept as-is unless `--ascii`. Invalid input fails with `file:line:col` and the
parser's message instead of a traceback. Unlike plain `json.loads`, it also
rejects what isn't valid JSON but Python accepts silently: `NaN`/`Infinity`
and, with `--strict-keys`, an object that repeats a key (where the last value
would quietly win).

`--lines` treats the input as JSON Lines: one value per line, blank lines
skipped, each record written compactly on its own line, errors reported with
their line number. `--check` writes nothing and exits 1 when the file is valid
but not already formatted that way (handy in CI).

    python -m minitools.jsonfmt response.json --sort-keys -o pretty.json
    python -m minitools.jsonfmt config.json --check --strict-keys
    python -m minitools.jsonfmt events.jsonl --lines --sort-keys
    curl -s https://example.com/api | python -m minitools.jsonfmt -

Exit codes: 0 ok, 1 --check found formatting differences (or the file is
missing), 2 invalid JSON or bad arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class JsonFmtError(ValueError):
    """Invalid input. ``str()`` gives ``line:col: message`` (or ``line: message``)."""

    def __init__(self, msg: str, lineno: int, colno: int | None = None):
        self.msg, self.lineno, self.colno = msg, lineno, colno
        where = f"{lineno}:{colno}" if colno is not None else f"{lineno}"
        super().__init__(f"{where}: {msg}")


def _no_constants(name: str):
    raise ValueError(f"{name} is not valid JSON")


def _pairs_hook(strict: bool):
    def hook(pairs: list[tuple[str, object]]) -> dict:
        out: dict = {}
        for key, value in pairs:
            if strict and key in out:
                raise ValueError(f"duplicate key {key!r}")
            out[key] = value
        return out
    return hook


def parse(text: str, strict_keys: bool = False, first_line: int = 1):
    """Parse one JSON document; raises JsonFmtError with the position on bad input.

    ``first_line`` is the file line ``text`` starts on (for JSON Lines records).
    Errors from the NaN/duplicate-key hooks carry no column: the decoder
    doesn't pass one to them.
    """
    try:
        return json.loads(text, parse_constant=_no_constants, object_pairs_hook=_pairs_hook(strict_keys))
    except json.JSONDecodeError as exc:
        raise JsonFmtError(exc.msg, first_line + exc.lineno - 1, exc.colno) from None
    except ValueError as exc:
        raise JsonFmtError(str(exc), first_line) from None


def dump(value, indent: int | None = 2, sort_keys: bool = False, ascii_only: bool = False) -> str:
    """Serialise ``value``; ``indent=None`` means compact (no spaces)."""
    seps = (",", ":") if indent is None else (",", ": ")
    return json.dumps(value, indent=indent, sort_keys=sort_keys, ensure_ascii=ascii_only, separators=seps)


def format_text(text: str, *, lines: bool = False, indent: int | None = 2, sort_keys: bool = False,
                ascii_only: bool = False, strict_keys: bool = False) -> str:
    """Return the formatted version of ``text`` (always ending with one newline)."""
    if not lines:
        if not text.strip():
            raise JsonFmtError("empty input", 1, 1)
        return dump(parse(text, strict_keys), indent, sort_keys, ascii_only) + "\n"
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        value = parse(line, strict_keys, first_line=no)
        out.append(dump(value, None, sort_keys, ascii_only))
    return "".join(f"{r}\n" for r in out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='JSON file, or "-" for stdin')
    layout = p.add_mutually_exclusive_group()
    layout.add_argument("--indent", type=int, default=2, help="spaces per level (default 2)")
    layout.add_argument("--compact", action="store_true", help="no indentation or spaces")
    p.add_argument("--lines", action="store_true", help="input is JSON Lines (one value per line)")
    p.add_argument("--sort-keys", action="store_true", help="sort object keys")
    p.add_argument("--ascii", action="store_true", help="escape non-ASCII characters as \\uXXXX")
    p.add_argument("--strict-keys", action="store_true", help="reject objects with a repeated key")
    p.add_argument("--check", action="store_true", help="write nothing; exit 1 if the file isn't formatted")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)
    if args.indent < 0 or args.indent > 8:
        p.error("--indent must be between 0 and 8")
    if args.check and args.output:
        p.error("--check writes nothing; drop -o")

    name = "<stdin>"
    if args.input == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.input)
        name = str(path)
        if not path.is_file():
            print(f"jsonfmt: no such file: {path}", file=sys.stderr)
            return 1
        if args.output and args.output.resolve() == path.resolve():
            print("jsonfmt: refusing to write over the input file", file=sys.stderr)
            return 2
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            print(f"jsonfmt: {path} is not valid UTF-8 (byte 0x{exc.object[exc.start]:02x} "
                  f"at offset {exc.start})", file=sys.stderr)
            return 2

    try:
        result = format_text(text, lines=args.lines, indent=None if args.compact else args.indent,
                             sort_keys=args.sort_keys, ascii_only=args.ascii, strict_keys=args.strict_keys)
    except JsonFmtError as exc:
        print(f"jsonfmt: {name}:{exc}", file=sys.stderr)
        return 2

    if args.check:
        if text.replace("\r\n", "\n") != result:
            print(f"jsonfmt: {name} would be reformatted", file=sys.stderr)
            return 1
        return 0
    if args.output:
        args.output.write_text(result, encoding="utf-8", newline="")
    else:
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

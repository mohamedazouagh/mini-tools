"""csvconvert - change a CSV's delimiter, encoding and line endings in one step.

Typical use: a semicolon-separated cp1252 export from Dutch/German Excel turned
into a plain UTF-8 comma CSV, or the other way round for colleagues who open
files by double-clicking them in Excel.

    python -m minitools.csvconvert export.csv --encoding cp1252 -o clean.csv
    python -m minitools.csvconvert data.csv --to ";" --bom --crlf -o for_excel.csv
    python -m minitools.csvconvert data.tsv -d tab --to , --info

The input delimiter is detected by default (`-d auto`): among `,` `;` tab and
`|`, the one that splits most of the first 20 rows into the header's number
(2 or more) of fields wins; files where none fits need `-d`. Quoted
cells (with delimiters or line breaks inside) survive the conversion, and rows
with a different number of fields than the header are kept but listed on
stderr with their line numbers. `--info` prints what was detected. Output is
UTF-8 (`--bom` adds the byte-order mark Excel looks for); writing over the
input file is refused.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

CANDIDATES = [",", ";", "\t", "|"]
NAMES = {"tab": "\t", "\\t": "\t", "comma": ",", "semicolon": ";", "pipe": "|"}
SAMPLE_ROWS = 20


def parse_delimiter(value: str) -> str:
    d = NAMES.get(value.lower(), value)
    if len(d) != 1:
        raise argparse.ArgumentTypeError(f"delimiter must be one character or tab/comma/semicolon/pipe, got {value!r}")
    return d


def detect_delimiter(text: str) -> str:
    """Pick the candidate delimiter that splits the first rows consistently.

    A candidate qualifies when the header has at least two fields and more
    than half of the sampled rows (header included) have that same number of
    fields, so one short or long row does not hide the real delimiter. The
    candidate with the most matching rows wins, then the one giving more
    fields, then the earlier candidate. Raises ValueError when none qualifies.
    """
    best, best_key = None, (0, 0)
    for d in CANDIDATES:
        rows = []
        for row in csv.reader(io.StringIO(text), delimiter=d):
            if row:
                rows.append(row)
            if len(rows) >= SAMPLE_ROWS:
                break
        if not rows or len(rows[0]) < 2:
            continue
        n = len(rows[0])
        matching = sum(len(r) == n for r in rows)
        if matching * 2 > len(rows) and (matching, n) > best_key:
            best, best_key = d, (matching, n)
    if best is None:
        raise ValueError("could not detect the delimiter; pass it with -d (e.g. -d ';' or -d tab)")
    return best


def convert(text: str, delimiter: str, out_delimiter: str, newline: str = "\n") -> tuple[str, list[tuple[int, int]], int, int]:
    """Re-write CSV text with another delimiter.

    Returns (output text, ragged rows as (line, fields), data rows, columns).
    Blank lines are dropped; the line number is where a row starts in the input.
    """
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=out_delimiter, lineterminator=newline)
    header: list[str] | None = None
    ragged: list[tuple[int, int]] = []
    count, start = 0, 1
    for row in reader:
        if row:
            if header is None:
                header = row
            else:
                count += 1
                if len(row) != len(header):
                    ragged.append((start, len(row)))
            writer.writerow(row)
        start = reader.line_num + 1
    return buf.getvalue(), ragged, count, len(header or [])


def _show(d: str) -> str:
    return "tab" if d == "\t" else repr(d)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", help='CSV file, or "-" for stdin')
    p.add_argument("-d", "--delimiter", default="auto", help="input delimiter, or 'auto' to detect it (default)")
    p.add_argument("--to", type=parse_delimiter, default=",", help="output delimiter (default ','; 'tab' for TSV)")
    p.add_argument("--encoding", default="utf-8-sig", help="input encoding, e.g. cp1252 (default UTF-8, BOM allowed)")
    p.add_argument("--bom", action="store_true", help="start the UTF-8 output with a byte-order mark (for Excel)")
    p.add_argument("--crlf", action="store_true", help="write Windows CRLF line endings instead of LF")
    p.add_argument("--info", action="store_true", help="print detected delimiter, rows and columns to stderr")
    p.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = p.parse_args(argv)
    try:
        "".encode(args.encoding)
    except LookupError:
        p.error(f"unknown encoding: {args.encoding}")
    delimiter = None
    if args.delimiter != "auto":
        try:
            delimiter = parse_delimiter(args.delimiter)
        except argparse.ArgumentTypeError as e:
            p.error(str(e))

    if args.input == "-":
        text = sys.stdin.read()
    else:
        path = Path(args.input)
        if not path.is_file():
            print(f"csvconvert: no such file: {path}", file=sys.stderr)
            return 1
        if args.output and args.output.resolve() == path.resolve():
            print("csvconvert: refusing to write over the input file; choose another -o", file=sys.stderr)
            return 2
        try:
            with path.open(encoding=args.encoding, newline="") as f:
                text = f.read()
        except UnicodeDecodeError as exc:
            print(
                f"csvconvert: {path} is not valid {exc.encoding} (byte 0x{exc.object[exc.start]:02x} at offset "
                f"{exc.start}); try --encoding cp1252 or --encoding latin-1",
                file=sys.stderr,
            )
            return 1
    text = text.removeprefix("\ufeff")
    if not text.strip():
        print("csvconvert: input has no header row", file=sys.stderr)
        return 1
    if delimiter is None:
        try:
            delimiter = detect_delimiter(text)
        except ValueError as e:
            print(f"csvconvert: {e}", file=sys.stderr)
            return 2

    out, ragged, rows, cols = convert(text, delimiter, args.to, "\r\n" if args.crlf else "\n")
    if args.info:
        print(
            f"csvconvert: delimiter {_show(delimiter)} -> {_show(args.to)}, {rows} rows, {cols} columns, "
            f"encoding {args.encoding} -> utf-8{' with BOM' if args.bom else ''}",
            file=sys.stderr,
        )
    for line, n in ragged[:5]:
        print(f"csvconvert: line {line}: {n} fields, header has {cols}", file=sys.stderr)
    if len(ragged) > 5:
        print(f"csvconvert: ... and {len(ragged) - 5} more rows with a different field count", file=sys.stderr)

    if args.bom:
        out = "\ufeff" + out
    if args.output:
        with args.output.open("w", encoding="utf-8", newline="") as f:
            f.write(out)
    else:
        # write bytes so the console encoding and Windows newline translation cannot alter the output
        stream = getattr(sys.stdout, "buffer", None)
        if stream is None:
            sys.stdout.write(out)
        else:
            sys.stdout.flush()
            stream.write(out.encode("utf-8"))
            stream.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

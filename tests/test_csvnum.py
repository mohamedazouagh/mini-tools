import io
from decimal import Decimal

import pytest

from minitools.csvnum import ColumnError, format_number, main, normalise_rows, parse_number, pick_columns


def read(text, decimal="auto"):
    value = parse_number(text, decimal)
    return None if value is None else format_number(value)


@pytest.mark.parametrize("text, expected", [
    ("1234.50", "1234.50"),
    ("1.234,50", "1234.50"),
    ("1,234.50", "1234.50"),
    ("1.234.567", "1234567"),
    ("1,234,567.8", "1234567.8"),
    ("0,5", "0.5"),
    (".5", "0.5"),
    ("€ 1 234,50", "1234.50"),
    ("1 234,5", "1234.5"),
    ("1'234.75", "1234.75"),
    ("EUR 12,00", "12.00"),
    ("12.00 USD", "12.00"),
    ("$-3.5", "-3.5"),
    ("-€3,50", "-3.50"),
    ("(12.00)", "-12.00"),
    ("12.00-", "-12.00"),
    ("+7", "7"),
    ("-0,00", "0.00"),
    ("007", "7"),
])
def test_auto_reads_common_formats(text, expected):
    assert read(text) == expected


@pytest.mark.parametrize("text", [
    "1,234",        # thousands or decimal? not guessed
    "1.234",
    "12.34.5",      # broken grouping
    "1,23,456",
    "1 23",         # space groups must be three digits
    "1 234.567,8",  # both marks after space grouping
    "abc", "12abc", "1e5", "--5", "-", "€", "12%", "",
])
def test_auto_rejects_ambiguous_or_invalid(text):
    assert parse_number(text) is None


def test_explicit_decimal_mark_resolves_ambiguity():
    assert read("1,234", "dot") == "1234"
    assert read("1,234", "comma") == "1.234"
    assert read("1.234", "comma") == "1234"
    assert read("1.234,5", "comma") == "1234.5"
    assert read("1,234.5", "dot") == "1234.5"
    assert read("1,5", "dot") is None          # a comma that is not a thousands separator
    assert read("1.234.567", "dot") is None    # several decimal points
    assert read("1.234.567", "comma") == "1234567"
    assert parse_number("1.234,5", "dot") is None


def test_parse_number_returns_exact_decimals():
    assert parse_number("0,10") + parse_number("0,20") == Decimal("0.30")


def test_normalise_rows_keeps_blanks_short_rows_and_reports_bad_cells():
    rows = [(2, ["a", "1.234,50", "x"]), (3, ["b", "  ", "y"]), (4, ["c"]), (5, ["d", "n/a", "z"])]
    out, bad = normalise_rows(rows, [1])
    assert out == [["a", "1234.50", "x"], ["b", "  ", "y"], ["c"], ["d", "n/a", "z"]]
    assert bad == [(5, 1, "n/a")]
    assert rows[0][1][1] == "1.234,50"  # input not mutated


def test_pick_columns():
    assert pick_columns(["balance,amount"], ["date", "amount", "balance"]) == [1, 2]
    with pytest.raises(ColumnError, match="unknown column\\(s\\): amt; available: date, amount"):
        pick_columns(["amt"], ["date", "amount"])


def test_cli_semicolon_bank_export(tmp_path, capsys):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text(
        "﻿date;amount;balance;note\n"
        '2026-10-01;-12,50;1.234,56;"coffee; cake"\n'
        "2026-10-02;1.000,00;2.234,56;salary\n"
        "2026-10-03;;2.234,56;\n",
        encoding="utf-8",
    )
    assert main([str(src), "-c", "amount,balance", "--decimal", "comma", "-d", ";", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == [
        "date;amount;balance;note",
        '2026-10-01;-12.50;1234.56;"coffee; cake"',
        "2026-10-02;1000.00;2234.56;salary",
        "2026-10-03;;2234.56;",
    ]
    assert capsys.readouterr().err == ""


def test_cli_reports_bad_cells_with_line_numbers_and_strict_fails(tmp_path, capsys, monkeypatch):
    data = 'id,price\n1,"1,234"\n2,"multi\nline"\n3,9.99\n'
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    assert main(["-", "-c", "price"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines()[-1] == "3,9.99"
    assert "line 2, price: cannot read '1,234'" in err
    assert "line 3, price: cannot read 'multi\\nline'" in err  # line where the row starts
    dst = tmp_path / "out.csv"
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    assert main(["-", "-c", "price", "--strict", "-o", str(dst)]) == 1
    assert "2 unreadable cells, nothing written" in capsys.readouterr().err
    assert not dst.exists()


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,amount\n1,2\n", encoding="utf-8")
    assert main([str(src), "-c", "amt"]) == 2
    assert "available: id, amount" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-c", "amount"]) == 1
    (tmp_path / "empty.csv").write_text("", encoding="utf-8")
    assert main([str(tmp_path / "empty.csv"), "-c", "amount"]) == 1

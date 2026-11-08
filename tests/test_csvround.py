import io

import pytest

from minitools.csvround import ColumnError, main, pick_columns, round_cell, round_rows


@pytest.mark.parametrize("text, places, expected", [
    ("2.675", 2, "2.68"),            # float round(2.675, 2) gives 2.67
    ("0.30000000000000004", 2, "0.30"),
    ("12.5", 2, "12.50"),            # padded to exactly N decimals
    ("7", 2, "7.00"),
    (" 3.14159 ", 3, "3.142"),
    (".5", 0, "1"),
    ("-2.5", 0, "-3"),               # half-up goes away from zero
    ("-0.001", 2, "0.00"),           # no negative zero
    ("+4.25", 1, "4.3"),
    ("1234.5", -2, "1200"),
    ("1250", -2, "1300"),
    ("98765432109876543210.125", 2, "98765432109876543210.13"),  # no precision loss
])
def test_half_up(text, places, expected):
    assert round_cell(text, places) == expected


@pytest.mark.parametrize("mode, values, expected", [
    ("half-even", ["0.125", "0.135", "-0.125", "2.5"], ["0.12", "0.14", "-0.12", "2.50"]),
    ("down", ["1.999", "-1.999"], ["1.99", "-1.99"]),
    ("floor", ["1.999", "-1.991"], ["1.99", "-2.00"]),
    ("ceiling", ["1.001", "-1.999"], ["1.01", "-1.99"]),
])
def test_modes(mode, values, expected):
    assert [round_cell(v, 2, mode) for v in values] == expected


@pytest.mark.parametrize("text", ["abc", "1,5", "1.234,50", "€12", "1e5", "nan", "inf", "--1", "1.2.3", "."])
def test_non_plain_numbers_rejected(text):
    assert round_cell(text) is None


def test_round_rows_keeps_empty_short_and_reports_bad():
    rows = [(2, ["a", "1.005", "x"]), (3, ["b", "", "y"]), (4, ["c"]), (5, ["d", "n/a", "z"])]
    out, bad = round_rows(rows, [1], 2)
    assert out == [["a", "1.01", "x"], ["b", "", "y"], ["c"], ["d", "n/a", "z"]]
    assert bad == [(5, 1, "n/a")]


def test_pick_columns_unknown_and_empty():
    assert pick_columns(["b, a", "b"], ["a", "b", "c"]) == [0, 1]
    with pytest.raises(ColumnError, match="available: a, b"):
        pick_columns(["zz"], ["a", "b"])
    with pytest.raises(ColumnError):
        pick_columns([" , "], ["a"])


def run(capsys, monkeypatch, text, *args):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    code = main(["-", *args])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_rounds_selected_columns_only(capsys, monkeypatch):
    code, out, err = run(capsys, monkeypatch, "id,amount,vat\n1,10.125,2.12625\n2,3,0.6300001\n",
                         "-c", "amount,vat")
    assert code == 0 and err == ""
    assert out == "id,amount,vat\n1,10.13,2.13\n2,3.00,0.63\n"


def test_cli_places_mode_and_delimiter(capsys, monkeypatch):
    code, out, _ = run(capsys, monkeypatch, "k;v\na;0.25\nb;0.35\n",
                       "-c", "v", "-p", "1", "--mode", "half-even", "-d", ";")
    assert code == 0
    assert out == "k;v\na;0.2\nb;0.4\n"


def test_cli_reports_bad_cells_with_line_numbers(capsys, monkeypatch):
    text = 'id,amount,note\n1,"1.5","two\nlines"\n2,abc,x\n'
    code, out, err = run(capsys, monkeypatch, text, "-c", "amount")
    assert code == 0
    assert "line 4, amount: not a plain number 'abc'" in err
    assert out == 'id,amount,note\n1,1.50,"two\nlines"\n2,abc,x\n'


def test_cli_strict_writes_nothing(capsys, monkeypatch):
    code, out, err = run(capsys, monkeypatch, "v\n1\nx\n", "-c", "v", "--strict")
    assert code == 1 and out == ""
    assert "1 non-numeric cell, nothing written" in err


def test_cli_unknown_column_exit_2(capsys, monkeypatch):
    code, _, err = run(capsys, monkeypatch, "a,b\n1,2\n", "-c", "c")
    assert code == 2 and "available: a, b" in err


def test_cli_file_output_and_refuses_to_overwrite(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("﻿v\n1.239\n", encoding="utf-8")
    dst = tmp_path / "out.csv"
    assert main([str(src), "-c", "v", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "v\n1.24\n"
    assert main([str(src), "-c", "v", "-o", str(src)]) == 2
    assert "refusing" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-c", "v"]) == 1

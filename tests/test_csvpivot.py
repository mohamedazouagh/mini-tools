import io

import pytest

from minitools.csvmelt import melt
from minitools.csvpivot import PivotError, main, pivot, plan_columns

HEADER = ["store", "month", "sales"]
ROWS = [
    ["Breda", "jan", "10"], ["Breda", "feb", "12"],
    ["Gouda", "jan", "7"], ["Gouda", "mar", "9"],
]


def test_plan_columns():
    assert plan_columns(HEADER, ["store"], "month", "sales") == ([0], 1, 2)
    with pytest.raises(PivotError, match="unknown column\\(s\\): qty; available: store, month, sales"):
        plan_columns(HEADER, ["store"], "month", "qty")
    with pytest.raises(PivotError, match="must all be different"):
        plan_columns(HEADER, ["store"], "store", "sales")
    with pytest.raises(PivotError, match="duplicate header"):
        plan_columns(["a", "a", "b"], [], "a", "b")


def test_pivot_keeps_first_seen_order_and_leaves_gaps_empty():
    assert pivot(HEADER, ROWS, [0], 1, 2) == [
        ["store", "jan", "feb", "mar"],
        ["Breda", "10", "12", ""],
        ["Gouda", "7", "", "9"],
    ]
    assert pivot(HEADER, ROWS, [0], 1, 2, fill="0")[1] == ["Breda", "10", "12", "0"]


def test_round_trip_with_csvmelt():
    wide_header = ["store", "jan", "feb"]
    wide = [["Breda", "10", "12"], ["Gouda", "7", "8"]]
    long = melt(wide_header, wide, [0], [1, 2])
    assert pivot(long[0], long[1:], [0], 1, 2) == [wide_header] + wide


def test_duplicates_error_by_default_or_keep_first_last():
    rows = ROWS + [["Breda", "jan", "99"]]
    with pytest.raises(PivotError, match="line 6: duplicate entry for Breda / jan"):
        pivot(HEADER, rows, [0], 1, 2)
    assert pivot(HEADER, rows, [0], 1, 2, keep="first")[1] == ["Breda", "10", "12", ""]
    assert pivot(HEADER, rows, [0], 1, 2, keep="last")[1] == ["Breda", "99", "12", ""]


def test_keys_trimmed_short_rows_and_no_id_columns():
    rows = [[" Breda ", " jan", "10"], ["Breda", "feb"]]
    assert pivot(HEADER, rows, [0], 1, 2) == [["store", "jan", "feb"], ["Breda", "10", ""]]
    assert pivot(HEADER, ROWS[:2], [], 1, 2) == [["jan", "feb"], ["10", "12"]]


def test_blank_or_clashing_new_headers_rejected():
    with pytest.raises(PivotError, match="line 3: blank value in column 'month'"):
        pivot(HEADER, [["Breda", "jan", "1"], ["Breda", " ", "2"]], [0], 1, 2)
    with pytest.raises(PivotError, match="clash with id columns: store"):
        pivot(HEADER, [["Breda", "store", "1"]], [0], 1, 2)


def test_cli_file_semicolons_fill(tmp_path):
    src, dst = tmp_path / "long.csv", tmp_path / "wide.csv"
    src.write_text("﻿id;q;score\n1;a;5\n1;b;3\n2;b;4\n", encoding="utf-8")
    assert main([str(src), "-i", "id", "-c", "q", "-v", "score", "--fill", "0", "-d", ";", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "id;a;b\n1;5;3\n2;0;4\n"


def test_cli_stdin_keeps_quoting(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('id,field,text\n1,note,"hi, there"\n'))
    assert main(["-", "-i", "id", "-c", "field", "-v", "text"]) == 0
    assert capsys.readouterr().out == 'id,note\n1,"hi, there"\n'


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,k,v\n1,a,2\n1,a,3\n", encoding="utf-8")
    assert main([str(src), "-i", "id", "-c", "k", "-v", "v"]) == 2
    assert "--keep first or --keep last" in capsys.readouterr().err
    assert main([str(src), "-i", "id", "-c", "k", "-v", "v", "--keep", "last"]) == 0
    assert capsys.readouterr().out == "id,a\n1,3\n"
    gappy = tmp_path / "gappy.csv"
    gappy.write_text("id,k,v\n\n1,a,2\n\n1,a,3\n", encoding="utf-8")
    assert main([str(gappy), "-i", "id", "-c", "k", "-v", "v"]) == 2
    assert "line 5: duplicate entry for 1 / a" in capsys.readouterr().err  # blank lines still counted
    assert main([str(src), "-i", "uid", "-c", "k", "-v", "v"]) == 2
    assert main([str(tmp_path / "missing.csv"), "-c", "k", "-v", "v"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty), "-c", "k", "-v", "v"]) == 1

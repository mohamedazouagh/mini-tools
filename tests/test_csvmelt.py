import io

import pytest

from minitools.csvmelt import ColumnError, main, melt, plan_columns

HEADER = ["store", "jan", "feb", "mar"]
ROWS = [["Breda", "10", "12", ""], ["Gouda", "7", " ", "9"]]


def test_values_default_to_all_non_id_columns():
    assert plan_columns(HEADER, ["store"], []) == ([0], [1, 2, 3])
    assert plan_columns(HEADER, ["store"], ["mar", "jan"]) == ([0], [3, 1])
    assert plan_columns(HEADER, [], ["feb"]) == ([], [2])


def test_melt_one_row_per_value_cell():
    assert melt(HEADER, ROWS, [0], [1, 2, 3], "month", "sales") == [
        ["store", "month", "sales"],
        ["Breda", "jan", "10"], ["Breda", "feb", "12"], ["Breda", "mar", ""],
        ["Gouda", "jan", "7"], ["Gouda", "feb", " "], ["Gouda", "mar", "9"],
    ]


def test_skip_blank_drops_empty_and_space_only_cells():
    out = melt(HEADER, ROWS, [0], [1, 2, 3], skip_blank=True)
    assert out[1:] == [["Breda", "jan", "10"], ["Breda", "feb", "12"], ["Gouda", "jan", "7"], ["Gouda", "mar", "9"]]


def test_short_rows_are_padded():
    assert melt(HEADER, [["Delft", "4"]], [0], [1, 2])[1:] == [["Delft", "jan", "4"], ["Delft", "feb", ""]]


def test_column_errors():
    with pytest.raises(ColumnError, match="unknown column\\(s\\): apr; available: store, jan, feb, mar"):
        plan_columns(HEADER, ["store"], ["apr"])
    with pytest.raises(ColumnError, match="both id and value: jan"):
        plan_columns(HEADER, ["store", "jan"], ["jan"])
    with pytest.raises(ColumnError, match="no value columns"):
        plan_columns(["a", "b"], ["a", "b"], [])
    with pytest.raises(ColumnError, match="duplicate header\\(s\\): x"):
        plan_columns(["id", "x", "x"], ["id"], [])


def test_cli_semicolon_file_with_names(tmp_path):
    src, dst = tmp_path / "wide.csv", tmp_path / "long.csv"
    src.write_text("﻿store;jan;feb\nBreda;10;12\n", encoding="utf-8")
    assert main([str(src), "-i", "store", "--var-name", "month", "--value-name", "sales", "-d", ";", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "store;month;sales\nBreda;jan;10\nBreda;feb;12\n"


def test_cli_stdin_keeps_quoting(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('id,note,score\n1,"hi, there",5\n'))
    assert main(["-", "-i", "id", "-v", "note,score"]) == 0
    assert capsys.readouterr().out == 'id,variable,value\n1,note,"hi, there"\n1,score,5\n'


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,a\n1,2\n", encoding="utf-8")
    assert main([str(src), "-i", "uid"]) == 2
    assert "available: id, a" in capsys.readouterr().err
    assert main([str(src), "-i", "id", "--var-name", "id"]) == 2
    assert main([str(src), "-i", "id", "--var-name", "x", "--value-name", "x"]) == 2
    assert main([str(tmp_path / "missing.csv"), "-i", "id"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty)]) == 1

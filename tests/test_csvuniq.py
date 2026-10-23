import io

import pytest

from minitools.csvuniq import ColumnError, duplicate_rows, main, resolve_columns, unique_rows

ROWS = [
    ["1", "ana", "3"],
    ["2", "bo", "1"],
    ["1", "ana", "4"],  # customer 1 again, newer count
    ["3", "cy", "0"],
    [" 2 ", "bo", "2"],  # key with spaces is still customer 2
]


def test_keep_first_keeps_earliest_row_per_key():
    assert unique_rows(ROWS, [0]) == [["1", "ana", "3"], ["2", "bo", "1"], ["3", "cy", "0"]]


def test_keep_last_keeps_final_row_at_its_position():
    assert unique_rows(ROWS, [0], keep="last") == [["1", "ana", "4"], ["3", "cy", "0"], [" 2 ", "bo", "2"]]


def test_multi_column_key_and_ignore_case():
    rows = [["a@x.nl", "NL"], ["A@X.nl", "NL"], ["a@x.nl", "BE"]]
    assert unique_rows(rows, [0, 1]) == rows
    assert unique_rows(rows, [0, 1], ignore_case=True) == [["a@x.nl", "NL"], ["a@x.nl", "BE"]]


def test_short_rows_have_blank_key_cells():
    rows = [["1"], ["1", ""], ["2", "x"]]
    assert unique_rows(rows, [1]) == [["1"], ["2", "x"]]


def test_duplicate_rows_lists_every_copy_in_order():
    assert duplicate_rows(ROWS, [0]) == [["1", "ana", "3"], ["2", "bo", "1"], ["1", "ana", "4"], [" 2 ", "bo", "2"]]
    assert duplicate_rows([["1"], ["2"]], [0]) == []


def test_bad_keep_and_columns():
    with pytest.raises(ValueError):
        unique_rows(ROWS, [0], keep="middle")
    with pytest.raises(ColumnError, match="unknown column\\(s\\): uid; available: id, name"):
        resolve_columns(["id", "name"], ["uid"])
    with pytest.raises(ColumnError, match="no key columns"):
        resolve_columns(["id"], [])


def test_cli_keep_last_semicolon_with_stats(tmp_path, capsys):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿id;name;orders\n1;ana;3\n2;bo;1\n1;ana;4\n", encoding="utf-8")
    assert main([str(src), "-k", "id", "--keep", "last", "-d", ";", "-o", str(dst), "--stats"]) == 0
    assert dst.read_text(encoding="utf-8") == "id;name;orders\n2;bo;1\n1;ana;4\n"
    assert "3 rows, 2 distinct keys, 2 rows kept" in capsys.readouterr().err


def test_cli_dupes_from_stdin_keeps_quoting(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('email,note\nA@x.nl,"hi, there"\nb@x.nl,\na@X.NL,again\n'))
    assert main(["-", "-k", "email", "-i", "--dupes"]) == 0
    assert capsys.readouterr().out == 'email,note\nA@x.nl,"hi, there"\na@X.NL,again\n'


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id\n1\n", encoding="utf-8")
    assert main([str(src), "-k", "uid"]) == 2
    assert "available: id" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-k", "id"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty), "-k", "id"]) == 1

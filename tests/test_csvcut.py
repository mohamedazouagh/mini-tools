import io

import pytest

from minitools.csvcut import ColumnError, cut_rows, main, plan_columns

HEADER = ["id", "name", "email", "notes"]


def test_keep_selects_and_reorders():
    assert plan_columns(HEADER, keep=["email", "id"]) == [2, 0]


def test_drop_keeps_original_order():
    assert plan_columns(HEADER, drop=["notes", "name"]) == [0, 2]


def test_unknown_column_lists_available_headers():
    with pytest.raises(ColumnError, match="unknown column\\(s\\): mail; available: id, name, email, notes"):
        plan_columns(HEADER, keep=["mail"])


def test_dropping_everything_is_an_error():
    with pytest.raises(ColumnError, match="no columns left"):
        plan_columns(["a"], drop=["a"])


def test_short_rows_are_padded():
    assert cut_rows([["1", "Ana"], ["2"]], [1, 0]) == [["Ana", "1"], ["", "2"]]


def test_cli_keep_with_semicolons(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿id;name;email\n1;Ana;a@example.com\n\n2;Bo;b@example.com\n", encoding="utf-8")
    assert main([str(src), "-c", "email, id", "-d", ";", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "email;id\na@example.com;1\nb@example.com;2\n"


def test_cli_exclude_from_stdin_keeps_quoting(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('id,notes,city\n1,"hi, there",Breda\n'))
    assert main(["-", "-x", "id"]) == 0
    assert capsys.readouterr().out == 'notes,city\n"hi, there",Breda\n'


def test_cli_unknown_column_exit_code(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main([str(src), "-c", "z"]) == 2
    assert "unknown column(s): z" in capsys.readouterr().err


def test_cli_missing_file_and_empty_input(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv"), "-c", "a"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty), "-c", "a"]) == 1
    err = capsys.readouterr().err
    assert "no such file" in err and "no header row" in err


def test_columns_and_exclude_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "x.csv"), "-c", "a", "-x", "b"])

import io

import pytest

from minitools.csvlook import display_width, main, numeric_columns, render, truncate


def test_text_table_aligns_and_right_aligns_numbers():
    out = render(["name", "amount"], [["Ana", "5"], ["Bartholomew", "1250.5"]])
    assert out == (
        "name         amount\n"
        "-----------  ------\n"
        "Ana               5\n"
        "Bartholomew  1250.5\n"
    )


def test_numeric_detection_ignores_empty_cells_but_not_text():
    rows = [["1", "a", ""], ["", "2", ""], ["-3.5e2", "x", ""]]
    assert numeric_columns(rows, 3) == [True, False, False]
    assert numeric_columns([["12%"], ["nan"]], 1) == [False]


def test_markdown_escapes_pipes_and_marks_numeric_columns():
    out = render(["id", "note"], [["7", "a|b"]], markdown=True)
    assert out == (
        "| id  | note |\n"
        "| --: | ---- |\n"
        "|   7 | a\\|b |\n"
    )


def test_short_rows_padded_and_newlines_flattened():
    out = render(["a", "b"], [["x"], ["multi\nline", "y"]])
    assert out.splitlines()[2] == "x"
    assert out.splitlines()[3] == "multi line  y"


def test_truncate_uses_ellipsis_and_display_width():
    assert truncate("abcdefgh", 5) == "abcd…"
    assert truncate("abc", 5) == "abc"
    assert display_width("日本") == 4
    assert truncate("日本語テキスト", 5) == "日本…"


def test_wide_characters_keep_columns_aligned():
    lines = render(["city", "n"], [["東京", "1"], ["Breda", "22"]]).splitlines()
    assert lines[2] == "東京    1"
    assert lines[3] == "Breda  22"


def test_cli_limits_rows_and_reports_on_stderr(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("﻿id;city\n1;Breda\n\n2;Gouda\n3;Delft\n", encoding="utf-8")
    assert main([str(src), "-n", "2", "-d", ";"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["id  city", "--  -----", " 1  Breda", " 2  Gouda"]
    assert "showing 2 of 3 rows" in captured.err


def test_cli_markdown_from_stdin_with_max_width(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("name,bio\nAna,likes long walks on the beach\n"))
    assert main(["-", "--markdown", "--max-width", "10", "-n", "0"]) == 0
    captured = capsys.readouterr()
    assert "| Ana  | likes lon… |" in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("args,code,message", [
    (["-n", "-1"], 2, "--rows must be 0 or more"),
    (["--max-width", "0"], 2, "--max-width must be at least 1"),
])
def test_cli_rejects_bad_options(tmp_path, capsys, args, code, message):
    src = tmp_path / "in.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    assert main([str(src), *args]) == code
    assert message in capsys.readouterr().err


def test_cli_missing_file_and_empty_input(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv")]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty)]) == 1
    err = capsys.readouterr().err
    assert "no such file" in err and "no header row" in err

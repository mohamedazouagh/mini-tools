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


def test_select_columns_reorders_trims_and_pads_short_rows():
    from minitools.csvlook import select_columns

    header, rows = select_columns([" id", "name ", "amount"], [["1", "Ada", "5"], ["2"]], ["amount", " id"])
    assert header == ["amount", " id"]
    assert rows == [["5", "1"], ["", "2"]]


def test_select_columns_unknown_or_empty_names():
    from minitools.csvlook import select_columns

    with pytest.raises(KeyError, match=r"unknown column\(s\): nope \(available: id, name\)"):
        select_columns(["id", "name"], [], ["id", "nope"])
    with pytest.raises(KeyError, match="no column names"):
        select_columns(["id"], [], [" ", ""])


def test_main_columns_flag(tmp_path, capsys):
    f = tmp_path / "s.csv"
    f.write_text("id,country,amount\n1,NL,10\n2,BE,250\n", encoding="utf-8")
    assert main([str(f), "-c", "amount,country"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "amount  country"
    assert out[2] == "    10  NL"
    assert main([str(f), "-c", "price"]) == 2
    assert "unknown column(s): price (available: id, country, amount)" in capsys.readouterr().err


def test_cli_encoding_previews_cp1252_file(tmp_path, capsys):
    src = tmp_path / "legacy.csv"
    src.write_bytes("naam;stad\nZoë;Café Noord\n".encode("cp1252"))
    assert main([str(src), "-d", ";", "--encoding", "cp1252"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("naam  stad")
    assert "Zoë   Café Noord" in out


def test_cli_undecodable_input_is_a_clear_error(tmp_path, capsys):
    src = tmp_path / "legacy.csv"
    src.write_bytes("id,name\n1,Zoë\n".encode("cp1252"))
    assert main([str(src)]) == 1
    err = capsys.readouterr().err
    assert "is not valid utf-8" in err and "byte 0xeb at offset 12" in err and "--encoding cp1252" in err


def test_cli_unknown_encoding_rejected(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([str(src), "--encoding", "nope-42"])
    assert exc.value.code == 2
    assert "unknown encoding: nope-42" in capsys.readouterr().err

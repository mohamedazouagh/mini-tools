import io

import pytest

from minitools.csvsplitcol import ColumnError, main, plan_header, split_cell, split_rows


def test_split_cell_keeps_rest_in_last_part_and_trims():
    assert split_cell("Den Haag, Zuid-Holland, NL", 2, ",") == ["Den Haag", "Zuid-Holland, NL"]
    assert split_cell(" Breda ,  NL ", 2, ",") == ["Breda", "NL"]


def test_split_cell_pads_short_and_blank_cells():
    assert split_cell("Breda", 3, ",") == ["Breda", "", ""]
    assert split_cell("   ", 2, ",") == ["", ""]


def test_whitespace_default_and_from_right():
    assert split_cell("Jan  van der   Berg", 2) == ["Jan", "van der   Berg"]
    assert split_cell("Jan van der Berg", 2, from_right=True) == ["Jan van der", "Berg"]
    assert split_cell("Berg", 2, from_right=True) == ["", "Berg"]  # padding on the left
    assert split_cell("report.final.csv", 2, ".", from_right=True) == ["report.final", "csv"]


def test_plan_header_replaces_or_keeps_column():
    assert plan_header(["id", "loc", "x"], "loc", ["city", "cc"], keep=False) == (1, ["id", "city", "cc", "x"])
    assert plan_header(["id", "loc", "x"], "loc", ["city", "cc"], keep=True) == (1, ["id", "loc", "city", "cc", "x"])
    # replacing a column with one of the same name is fine when it is not kept
    assert plan_header(["id", "date"], "date", ["date", "time"], keep=False)[1] == ["id", "date", "time"]


@pytest.mark.parametrize(
    "column, into, keep, message",
    [
        ("zone", ["a"], False, "unknown column: zone; available: id, loc, x"),
        ("loc", ["x"], False, "already exist: x"),
        ("loc", ["loc", "b"], True, "already exist: loc"),
        ("loc", ["a", "a"], False, "repeats: a"),
        ("loc", ["a", ""], False, "non-empty"),
    ],
)
def test_plan_header_rejects_bad_names(column, into, keep, message):
    with pytest.raises(ColumnError, match=message):
        plan_header(["id", "loc", "x"], column, into, keep)


def test_split_rows_counts_short_cells_and_pads_short_rows():
    rows = [["1", "Breda, NL"], ["2", "Gouda"], ["3", ""], ["4"]]
    out, short = split_rows(rows, 1, 2, ",")
    assert out == [["1", "Breda", "NL"], ["2", "Gouda", ""], ["3", "", ""], ["4", "", ""]]
    assert short == 1  # blank cells are not counted as short
    assert rows[1] == ["2", "Gouda"]


def test_cli_semicolon_file_keeps_quoting(tmp_path, capsys):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text('﻿id;location;n\n1;"Breda; centrum, NL";3\n2;Delft;4\n', encoding="utf-8")
    assert main([str(src), "-c", "location", "--sep", ",", "--into", "place,country", "-d", ";", "-o", str(dst), "--stats"]) == 0
    assert dst.read_text(encoding="utf-8") == 'id;place;country;n\n1;"Breda; centrum";NL;3\n2;Delft;;4\n'
    assert "split 2 rows, 1 with fewer than 2 parts" in capsys.readouterr().err


def test_cli_stdin_from_right_keep(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("name\nAna de Vries\nBo\n"))
    assert main(["-", "-c", "name", "--into", "first,last", "--from-right", "--keep"]) == 0
    assert capsys.readouterr().out == "name,first,last\nAna de Vries,Ana de,Vries\nBo,,Bo\n"


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main([str(src), "-c", "z", "--into", "x,y"]) == 2
    assert "available: a, b" in capsys.readouterr().err
    assert main([str(src), "-c", "a", "--into", "x", "--sep", ""]) == 2
    assert main([str(tmp_path / "missing.csv"), "-c", "a", "--into", "x"]) == 1

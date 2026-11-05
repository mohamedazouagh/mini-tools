import io

import pytest

from minitools.csvmergecol import ColumnError, main, merge_cells, merge_rows, plan_header


def test_merge_cells_trims_and_skips_blanks():
    assert merge_cells([" Ana ", " de Vries"]) == "Ana de Vries"
    assert merge_cells(["Ana", "  "]) == "Ana"
    assert merge_cells(["", ""]) == ""
    assert merge_cells(["Markt", "12", "Breda"], ", ") == "Markt, 12, Breda"


def test_merge_cells_keep_blank():
    assert merge_cells(["a", "", "c"], ";", keep_blank=True) == "a;;c"
    assert merge_cells(["", " "], ";", keep_blank=True) == ""  # all blank stays empty


def test_plan_header_replace_and_keep():
    h = ["id", "first", "x", "last"]
    assert plan_header(h, ["first", "last"], "name", keep=False) == ([1, 3], ["id", "name", "x"])
    assert plan_header(h, ["first", "last"], "name", keep=True) == ([1, 3], ["id", "first", "x", "last", "name"])
    # -c order decides the merge order, the slot is still the leftmost source
    assert plan_header(h, ["last", "first"], "name", keep=False) == ([3, 1], ["id", "name", "x"])
    # reusing a source name is fine when the sources are dropped
    assert plan_header(["date", "time"], ["date", "time"], "date", keep=False)[1] == ["date"]


@pytest.mark.parametrize(
    "columns, into, keep, message",
    [
        (["first", "zz"], "n", False, r"unknown column\(s\): zz; available: id, first, x, last"),
        (["first", "first"], "n", False, "repeats: first"),
        (["first"], "n", False, "at least two"),
        (["first", "last"], "", False, "non-empty"),
        (["first", "last"], "x", False, "already exists: x"),
        (["first", "last"], "first", True, "already exists: first"),
    ],
)
def test_plan_header_rejects_bad_names(columns, into, keep, message):
    with pytest.raises(ColumnError, match=message):
        plan_header(["id", "first", "x", "last"], columns, into, keep)


def test_merge_rows_pads_short_rows_and_keeps_others():
    rows = [["1", "Ana", "NL", "Vries"], ["2", "Bo"], ["3", "", "BE", ""]]
    assert merge_rows(rows, [1, 3]) == [["1", "Ana Vries", "NL"], ["2", "Bo", ""], ["3", "", "BE"]]
    assert rows[1] == ["2", "Bo"]  # input not modified


def test_cli_semicolon_file_with_quoting(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿id;street;nr;city\n1;Markt;12;Breda\n2;\"Lange; Brug\";;Delft\n", encoding="utf-8")
    assert main([str(src), "-c", "street,nr,city", "--into", "address", "--sep", ", ", "-d", ";", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == 'id;address\n1;Markt, 12, Breda\n2;"Lange; Brug, Delft"\n'


def test_cli_stdin_keep(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("date,time,v\n2026-11-05,09:30,1\n"))
    assert main(["-", "-c", "date,time", "--into", "ts", "--sep", "T", "--keep"]) == 0
    assert capsys.readouterr().out == "date,time,ts,v\n2026-11-05,09:30,2026-11-05T09:30,1\n"


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main([str(src), "-c", "a,z", "--into", "x"]) == 2
    assert "available: a, b" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-c", "a,b", "--into", "x"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty), "-c", "a,b", "--into", "x"]) == 1

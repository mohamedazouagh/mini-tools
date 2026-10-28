import io

import pytest

from minitools.csvreplace import ColumnError, compile_pattern, main, pick_columns, replace_rows


def test_pick_columns_comma_lists_and_errors():
    header = ["id", "name", "phone", "country"]
    assert pick_columns(["phone,name"], header) == [1, 2]
    assert pick_columns(["country", " id , country"], header) == [0, 3]
    with pytest.raises(ColumnError, match="unknown column\\(s\\): mobile; available: id, name, phone, country"):
        pick_columns(["mobile"], header)


def test_replace_only_in_chosen_columns_with_counts():
    rows = [["1", "06-1234 5678", "06-1"], ["2", "+31 6 1111", "x"], ["3"], ["4", "0612", "y"]]
    out, changed = replace_rows(rows, [1], compile_pattern(r"[^0-9+]"), "")
    assert out == [["1", "0612345678", "06-1"], ["2", "+3161111", "x"], ["3"], ["4", "0612", "y"]]
    assert changed == {1: 2}
    assert rows[0][1] == "06-1234 5678"  # input not mutated


def test_groups_ignore_case_and_whole_cells():
    rows = [["nl"], ["Holland"], ["NLD"], ["the netherlands"]]
    rx = compile_pattern("nl|holland", ignore_case=True, whole=True)
    out, changed = replace_rows(rows, [0], rx, "NL", whole=True)
    assert [r[0] for r in out] == ["NL", "NL", "NLD", "the netherlands"]
    assert changed == {0: 2}
    rx = compile_pattern(r"(\d{2})-(\d{2})-(\d{4})")
    out, _ = replace_rows([["28-10-2026"], ["on 01-11-2026"]], [0], rx, r"\3-\2-\1")
    assert out == [["2026-10-28"], ["on 2026-11-01"]]
    rx = compile_pattern(r"(?P<d>\d+)", whole=True)
    assert replace_rows([["42"]], [0], rx, r"#\g<d>", whole=True)[0] == [["#42"]]


def test_literal_pattern_and_replacement():
    rx = compile_pattern(".", literal=True)
    out, _ = replace_rows([["1.50"], ["2"]], [0], rx, r"\1,", literal=True)
    assert out == [["1\\1,50"], ["2"]]  # neither "." nor "\1" is special


def test_cli_semicolons_quoting_and_count(tmp_path, capsys):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿id;price;note\n1;1.50;a.b\n2;2.75;\n3;3;c\n", encoding="utf-8")
    assert main([str(src), "-c", "price", "-p", ".", "-r", ";", "--literal", "-d", ";", "--count", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == ["id;price;note", '1;"1;50";a.b', '2;"2;75";', "3;3;c"]
    assert capsys.readouterr().err.strip() == "price: 2 cells changed"


def test_cli_all_columns_never_touch_header(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a x,b x\nx1,x2\n"))
    assert main(["-", "--all", "-p", "x", "-r", "y"]) == 0
    assert capsys.readouterr().out.splitlines() == ["a x,b x", "y1,y2"]


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,name\n1,ana\n", encoding="utf-8")
    assert main([str(src), "-c", "nmae", "-p", "a"]) == 2
    assert "available: id, name" in capsys.readouterr().err
    assert main([str(src), "-c", "name", "-p", "(a"]) == 2
    assert "bad pattern" in capsys.readouterr().err
    assert main([str(src), "-c", "name", "-p", "a", "-r", r"\2"]) == 2
    assert "bad replacement" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-c", "name", "-p", "a"]) == 1

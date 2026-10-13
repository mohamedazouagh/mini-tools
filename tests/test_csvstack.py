import pytest

from minitools.csvstack import StackError, main, read_table, stack


def test_read_table_skips_blank_lines_and_pads_short_rows():
    header, rows = read_table("id, name\n1,Ana\n\n2\n,\n")
    assert header == ["id", "name"]
    assert rows == [["1", "Ana"], ["2", ""]]


def test_read_table_rejects_long_rows_and_duplicate_headers():
    with pytest.raises(StackError, match="row 3 has 3 cells but the header has 2"):
        read_table("a,b\n1,2\n1,2,3\n", name="x.csv")
    with pytest.raises(StackError, match="duplicate column name\\(s\\): a"):
        read_table("a,b,a\n")
    with pytest.raises(StackError, match="no header row"):
        read_table("\n\n")


def test_stack_reorders_columns_to_match_first_file():
    cols, rows = stack([("a.csv", ["id", "x"], [["1", "p"]]), ("b.csv", ["x", "id"], [["q", "2"]])])
    assert cols == ["id", "x"]
    assert rows == [["1", "p"], ["2", "q"]]


def test_stack_strict_reports_missing_and_extra():
    with pytest.raises(StackError, match="b.csv: columns differ from a.csv \\(missing x; extra y\\); use --union"):
        stack([("a.csv", ["id", "x"], []), ("b.csv", ["id", "y"], [])])


def test_stack_union_fills_gaps_in_first_seen_order():
    cols, rows = stack(
        [("a.csv", ["id", "x"], [["1", "p"]]), ("b.csv", ["y", "id"], [["z", "2"]])], union=True
    )
    assert cols == ["id", "x", "y"]
    assert rows == [["1", "p", ""], ["2", "", "z"]]


def test_stack_source_column_and_clash():
    cols, rows = stack([("jan.csv", ["id"], [["1"]]), ("feb.csv", ["id"], [["2"]])], source="file")
    assert cols == ["file", "id"]
    assert rows == [["jan.csv", "1"], ["feb.csv", "2"]]
    with pytest.raises(StackError, match="already exists"):
        stack([("a.csv", ["id"], [])], source="id")


def test_cli_stacks_files_with_semicolons(tmp_path, capsys):
    (tmp_path / "jan.csv").write_text("﻿id;amount\n1;10\n", encoding="utf-8")
    (tmp_path / "feb.csv").write_text("amount;id\n20;2\n\n", encoding="utf-8")
    out = tmp_path / "all.csv"
    args = [str(tmp_path / "jan.csv"), str(tmp_path / "feb.csv"), "-d", ";", "--source", "file", "-o", str(out)]
    assert main(args) == 0
    assert out.read_text(encoding="utf-8") == "file;id;amount\njan.csv;1;10\nfeb.csv;2;20\n"
    assert "2 row(s) from 2 file(s)" in capsys.readouterr().err


def test_cli_errors(tmp_path, capsys):
    a = tmp_path / "a.csv"
    a.write_text("id,x\n1,2\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("id,y\n3,4\n", encoding="utf-8")
    assert main([str(a), str(tmp_path / "b.csv")]) == 2
    assert "use --union" in capsys.readouterr().err
    assert main([str(a), str(tmp_path / "missing.csv")]) == 2
    assert "no such file" in capsys.readouterr().err
    assert main([str(a), "-o", str(a)]) == 2
    assert "also an input" in capsys.readouterr().err
    assert a.read_text(encoding="utf-8") == "id,x\n1,2\n"

import io

import pytest

from minitools.csvfill import ColumnError, fill_rows, main, resolve_columns


def test_fill_down_uses_last_non_blank_value():
    rows = [["North", "A", "1"], ["", "B", "2"], ["  ", "", "3"], ["South", "C", ""], ["", "", "5"]]
    out, n = fill_rows(rows, [0, 1])
    assert out == [["North", "A", "1"], ["North", "B", "2"], ["North", "B", "3"], ["South", "C", ""], ["South", "C", "5"]]
    assert n == 5


def test_leading_blanks_stay_blank_and_input_is_not_mutated():
    rows = [["", "x"], ["a", "y"], ["", "z"]]
    out, n = fill_rows(rows, [0])
    assert out == [["", "x"], ["a", "y"], ["a", "z"]]
    assert n == 1
    assert rows[2] == ["", "z"]


def test_fixed_value_fills_every_blank_including_leading_ones():
    out, n = fill_rows([["", "1"], ["7", ""], ["8", " "]], [1], value="0")
    assert out == [["", "1"], ["7", "0"], ["8", "0"]]
    assert n == 2


def test_short_rows_are_padded():
    out, n = fill_rows([["a", "b", "c"], ["d"]], [2])
    assert out == [["a", "b", "c"], ["d", "", "c"]]
    assert n == 1


def test_unknown_column_lists_headers():
    with pytest.raises(ColumnError, match="unknown column\\(s\\): zone; available: region, store"):
        resolve_columns(["region", "store"], ["zone"])


def test_cli_columns_semicolon_file(tmp_path, capsys):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿region;store;sales\nNorth;Breda;10\n;Gouda;12\n;;7\n", encoding="utf-8")
    assert main([str(src), "-c", "region, store", "-d", ";", "-o", str(dst), "--stats"]) == 0
    assert dst.read_text(encoding="utf-8") == "region;store;sales\nNorth;Breda;10\nNorth;Gouda;12\nNorth;Gouda;7\n"
    assert "filled 3 cells in 3 rows" in capsys.readouterr().err


def test_cli_all_from_stdin_keeps_quoting(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('a,b\n"x, y",1\n,\n'))
    assert main(["-", "--all"]) == 0
    assert capsys.readouterr().out == 'a,b\n"x, y",1\n"x, y",1\n'


def test_cli_value_and_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,score\n1,\n2,5\n", encoding="utf-8")
    assert main([str(src), "-c", "score", "--value", "0"]) == 0
    assert capsys.readouterr().out == "id,score\n1,0\n2,5\n"
    assert main([str(src), "-c", "points"]) == 2
    assert "unknown column(s): points" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "--all"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty), "--all"]) == 1


def test_within_stops_values_crossing_into_the_next_group():
    rows = [["North", "Breda", "1"], ["", "", "2"], ["South", "", "3"], ["", "Gouda", "4"], ["", "", "5"]]
    plain, _ = fill_rows(rows, [0, 1])
    assert plain[2] == ["South", "Breda", "3"]  # without --within the store leaks across regions
    out, n = fill_rows(rows, [0, 1], within=0)
    assert out == [
        ["North", "Breda", "1"],
        ["North", "Breda", "2"],
        ["South", "", "3"],
        ["South", "Gouda", "4"],
        ["South", "Gouda", "5"],
    ]
    assert n == 5


def test_within_column_not_filled_itself():
    # group column is not in -c: groups are read as they are (blank is its own group)
    rows = [["A", "x"], ["A", ""], ["", ""], ["B", ""]]
    out, n = fill_rows(rows, [1], within=0)
    assert out == [["A", "x"], ["A", "x"], ["", ""], ["B", ""]]
    assert n == 1


def test_cli_within_and_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("region,store,sales\nNorth,Breda,1\nSouth,,2\n,Gouda,3\n,,4\n", encoding="utf-8")
    assert main([str(src), "-c", "region,store", "--within", "region"]) == 0
    assert capsys.readouterr().out == "region,store,sales\nNorth,Breda,1\nSouth,,2\nSouth,Gouda,3\nSouth,Gouda,4\n"
    assert main([str(src), "-c", "store", "--within", "zone"]) == 2
    assert "unknown column(s): zone" in capsys.readouterr().err
    assert main([str(src), "-c", "store", "--within", "region", "--value", "0"]) == 2
    assert "--within only applies to filling down" in capsys.readouterr().err


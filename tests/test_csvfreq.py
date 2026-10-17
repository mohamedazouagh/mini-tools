import io

import pytest

from minitools.csvfreq import BLANK, ColumnError, column_indexes, count_values, main

ROWS = [
    ["NL", "paid"],
    ["BE", "open"],
    [" NL ", "paid"],
    ["nl", "open"],
    ["", "paid"],
    ["DE"],  # short row: status is blank
]


def test_counts_most_common_first_with_value_tiebreak():
    assert count_values(ROWS, [0]) == [(("NL",), 2), ((BLANK,), 1), (("BE",), 1), (("DE",), 1), (("nl",), 1)]


def test_ignore_case_merges_and_shows_most_common_spelling():
    assert count_values(ROWS, [0], ignore_case=True)[0] == (("NL",), 3)


def test_no_blank_skips_empty_cells():
    assert all(key != (BLANK,) for key, _ in count_values(ROWS, [0], keep_blank=False))
    assert sum(n for _, n in count_values(ROWS, [0], keep_blank=False)) == 5


def test_column_combinations_and_short_rows():
    res = dict(count_values(ROWS, [0, 1]))
    assert res[("NL", "paid")] == 2
    assert res[("DE", BLANK)] == 1
    assert res[(BLANK, "paid")] == 1


def test_unknown_column_lists_headers():
    with pytest.raises(ColumnError, match="unknown column\\(s\\): land; available: country, status"):
        column_indexes(["country", "status"], ["land"])


def test_cli_table_with_semicolons_and_top(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("﻿country;status\nNL;paid\nBE;open\nNL;open\n\nNL;paid\n", encoding="utf-8")
    assert main([str(src), "-c", "country", "-d", ";", "-n", "1"]) == 0
    assert capsys.readouterr().out == "country  count  share\nNL           3  75.0%\n"


def test_cli_csv_output_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("city,x\nBreda,1\nbreda,2\n,3\n"))
    assert main(["-", "-c", "city", "-i", "--no-blank", "--csv"]) == 0
    assert capsys.readouterr().out == "city,count,share\nBreda,2,100.0\n"


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main([str(src), "-c", "z"]) == 2
    assert "unknown column(s): z" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-c", "a"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("a,b\n,2\n", encoding="utf-8")
    assert main([str(empty), "-c", "a", "--no-blank"]) == 1
    assert "no values to count" in capsys.readouterr().err


def test_sort_by_value_numbers_numerically_text_after_blank_last():
    from minitools.csvfreq import sort_by_value

    counted = [(("10",), 5), ((BLANK,), 4), (("b",), 3), (("2",), 2), (("A",), 2), (("1_000",), 1), (("nan",), 1)]
    assert [k[0] for k, _ in sort_by_value(counted)] == ["2", "10", "1_000", "A", "b", "nan", BLANK]


def test_cli_sort_value_applies_after_top(tmp_path, capsys):
    src = tmp_path / "ratings.csv"
    src.write_text("rating\n10\n2\n2\n10\n10\n9\n1\n", encoding="utf-8")
    assert main([str(src), "-c", "rating", "--sort", "value", "--csv"]) == 0
    assert capsys.readouterr().out.splitlines()[1:] == ["1,1,14.3", "2,2,28.6", "9,1,14.3", "10,3,42.9"]
    assert main([str(src), "-c", "rating", "-n", "2", "--sort", "value", "--csv"]) == 0
    assert capsys.readouterr().out.splitlines()[1:] == ["2,2,28.6", "10,3,42.9"]
    with pytest.raises(SystemExit):
        main([str(src), "-c", "rating", "--sort", "alpha"])

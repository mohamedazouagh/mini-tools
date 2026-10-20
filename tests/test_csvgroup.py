import io

import pytest

from minitools.csvgroup import BLANK, Agg, GroupError, build_table, main, parse_agg

HEADER = ["country", "status", "amount", "customer"]
ROWS = [
    (2, ["NL", "paid", "0.10", "ann"]),
    (3, [" NL ", "open", "0.20", "bob"]),
    (4, ["BE", "paid", "5", "ann"]),
    (5, ["NL", "paid", "", "ann"]),
    (6, ["", "paid", "1.5", "cy"]),
    (7, ["BE"]),  # short row
]


def test_parse_agg_specs():
    assert parse_agg("count") == Agg("count")
    assert parse_agg("amount:SUM") == Agg("sum", "amount")
    assert parse_agg("a:b:mean") == Agg("mean", "a:b")  # colon inside a column name
    for bad in ["amount", "amount:median", ":sum"]:
        with pytest.raises(GroupError, match="bad aggregate"):
            parse_agg(bad)


def test_count_sum_mean_min_max_distinct_with_exact_decimals():
    aggs = [Agg("count"), Agg("sum", "amount"), Agg("mean", "amount"), Agg("min", "amount"),
            Agg("max", "amount"), Agg("distinct", "customer")]
    table = build_table(HEADER, ROWS, ["country"], aggs)
    assert table[0] == ["country", "count", "amount_sum", "amount_mean", "amount_min", "amount_max", "customer_distinct"]
    assert table[1:] == [
        ["BE", "2", "5", "5.00", "5", "5", "1"],
        ["NL", "3", "0.30", "0.15", "0.10", "0.20", "2"],  # empty amount skipped, not counted as 0
        [BLANK, "1", "1.5", "1.50", "1.5", "1.5", "1"],
    ]


def test_group_without_numbers_gives_empty_cell():
    table = build_table(HEADER, [(2, ["DE", "open", "", "x"])], ["country"], [Agg("sum", "amount")])
    assert table[1] == ["DE", ""]


def test_multi_column_keys_sorted_numbers_numerically():
    rows = [(2, ["10", "a"]), (3, ["9", "b"]), (4, ["x", "a"]), (5, ["9", "b"])]
    table = build_table(["size", "tag"], rows, ["size", "tag"], [Agg("count")])
    assert table[1:] == [["9", "b", "2"], ["10", "a", "1"], ["x", "a", "1"]]


def test_non_number_reports_line_and_unknown_column_lists_headers():
    with pytest.raises(GroupError, match=r"line 9: 'n/a' in column 'amount' is not a number"):
        build_table(HEADER, [(9, ["NL", "paid", "n/a", "z"])], ["country"], [Agg("sum", "amount")])
    with pytest.raises(GroupError, match="unknown column\\(s\\): land, price; available: country"):
        build_table(HEADER, ROWS, ["land"], [Agg("sum", "price")])


def test_mean_precision_rounds_half_up():
    rows = [(2, ["a", "1"]), (3, ["a", "2"]), (4, ["a", "2"])]
    assert build_table(["k", "v"], rows, ["k"], [Agg("mean", "v")], precision=3)[1] == ["a", "1.667"]
    assert build_table(["k", "v"], rows[:2], ["k"], [Agg("mean", "v")], precision=0)[1] == ["a", "2"]


def test_cli_table_semicolons_bom_and_blank_lines(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("﻿country;amount\nNL;2.5\n\nBE;1\nNL;3\n", encoding="utf-8")
    assert main([str(src), "-g", "country", "-a", "count", "-a", "amount:sum", "-d", ";"]) == 0
    assert capsys.readouterr().out == (
        "country  count  amount_sum\n"
        "BE           1           1\n"
        "NL           2         5.5\n"
    )


def test_cli_csv_from_stdin_defaults_to_count(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("city\nGouda\nBreda\nGouda\n"))
    assert main(["-", "-g", "city", "--csv"]) == 0
    assert capsys.readouterr().out == "city,count\nBreda,1\nGouda,2\n"


def test_cli_bad_number_exit_2_with_file_line(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text('k,note,v\na,"two\nlines",1\nb,x,oops\n', encoding="utf-8")
    assert main([str(src), "-g", "k", "-a", "v:sum"]) == 2
    assert "line 4: 'oops'" in capsys.readouterr().err


def test_cli_missing_file_and_bad_agg(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv"), "-g", "k"]) == 1
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "nope.csv"), "-g", "k", "-a", "v:median"])
    assert exc.value.code == 2

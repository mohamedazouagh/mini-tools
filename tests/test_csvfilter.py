import io

import pytest

from minitools.csvfilter import ConditionError, filter_rows, main, parse_condition

HEADER = ["id", "country", "amount", "email"]
ROWS = [
    ["1", "NL", "120", "a@example.com"],
    ["2", "BE", "80.5", "b@test.org"],
    ["3", "nl", "n/a", "c@example.com"],
    ["4", "DE", "100", "d@EXAMPLE.com"],
    ["5", "NL"],  # short row
]


def ids(rows):
    return [r[0] for r in rows]


@pytest.mark.parametrize(
    "text,column,op,value",
    [
        ("amount>=100", "amount", ">=", "100"),
        (" country = NL ", "country", "=", "NL"),
        ("email!~@example", "email", "!~", "@example"),
        ("url=https://x.test/?a=b", "url", "=", "https://x.test/?a=b"),  # first operator splits
    ],
)
def test_parse_condition(text, column, op, value):
    c = parse_condition(text)
    assert (c.column, c.op, c.value) == (column, op, value)


def test_parse_errors():
    with pytest.raises(ConditionError, match="cannot parse"):
        parse_condition("amount")
    with pytest.raises(ConditionError, match="needs a number"):
        parse_condition("amount>lots")
    with pytest.raises(ConditionError, match="bad regex"):
        parse_condition("email~[")


def test_numeric_comparisons_skip_text_cells():
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("amount>=100")])) == ["1", "4"]
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("amount<100")])) == ["2"]


def test_equality_is_numeric_when_both_sides_are_numbers():
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("amount=100.0")])) == ["4"]
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("amount!=100")])) == ["1", "2", "3", "5"]


def test_case_sensitivity_and_regex():
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("country=NL")])) == ["1", "5"]
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("country=NL", ignore_case=True)])) == ["1", "3", "5"]
    assert ids(filter_rows(HEADER, ROWS, [parse_condition(r"email~@example\.com$")])) == ["1", "3"]
    assert ids(filter_rows(HEADER, ROWS, [parse_condition("email!~example", ignore_case=True)])) == ["2", "5"]


def test_all_vs_any():
    conds = [parse_condition("country=NL"), parse_condition("amount>100")]
    assert ids(filter_rows(HEADER, ROWS, conds)) == ["1"]
    assert ids(filter_rows(HEADER, ROWS, conds, any_match=True)) == ["1", "5"]


def test_unknown_column_lists_headers():
    with pytest.raises(ConditionError, match="unknown column\\(s\\): price; available: id, country, amount, email"):
        filter_rows(HEADER, ROWS, [parse_condition("price>1")])


def test_cli_writes_matching_rows_with_semicolons(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿id;country;amount\n1;NL;5\n\n2;BE;7\n3;NL;9\n", encoding="utf-8")
    assert main([str(src), "-d", ";", "-w", "country=NL", "-w", "amount>6", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "id;country;amount\n3;NL;9\n"


def test_cli_count_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('id,note\n1,"hello, world"\n2,bye\n'))
    assert main(["-", "-w", "note~hello", "--count"]) == 0
    assert capsys.readouterr().out == "1\n"


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main([str(src), "-w", "z=1"]) == 2
    assert main([str(src), "-w", "a>x"]) == 2
    assert main([str(tmp_path / "nope.csv"), "-w", "a=1"]) == 1
    err = capsys.readouterr().err
    assert "unknown column(s): z" in err and "needs a number" in err and "no such file" in err

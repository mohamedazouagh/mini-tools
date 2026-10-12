import io
import json

import pytest

from minitools.csv2json import HeaderError, convert_value, main, nest, rows_to_records


@pytest.mark.parametrize(
    "cell,expected",
    [
        ("42", 42),
        ("-3", -3),
        ("0", 0),
        ("2.50", 2.5),
        ("-0.1", -0.1),
        ("TRUE", True),
        ("false", False),
        ("", None),
        ("   ", None),
        ("007", "007"),  # leading zeros: IDs and postcodes stay text
        ("1e5", "1e5"),
        ("nan", "nan"),
        ("1,000", "1,000"),
        ("4811 AB", "4811 AB"),
    ],
)
def test_convert_value(cell, expected):
    assert convert_value(cell) == expected
    assert type(convert_value(cell)) is type(expected)


def test_records_keep_strings_by_default_and_pad_short_rows():
    rows = [["id", " name ", "zip"], ["1", "Ana", "007"], ["2"]]
    assert rows_to_records(rows) == [
        {"id": "1", "name": "Ana", "zip": "007"},
        {"id": "2", "name": "", "zip": ""},
    ]


def test_records_with_types():
    rows = [["id", "price", "active", "note"], ["1", "9.99", "true", ""]]
    assert rows_to_records(rows, types=True) == [{"id": 1, "price": 9.99, "active": True, "note": None}]


def test_nest_rebuilds_dotted_keys():
    assert nest({"id": 1, "address.city": "Breda", "address.geo.lat": 51.6}) == {
        "id": 1,
        "address": {"city": "Breda", "geo": {"lat": 51.6}},
    }


@pytest.mark.parametrize("record", [{"a": 1, "a.b": 2}, {"a.b": 2, "a": 1}])
def test_nest_conflicts_are_errors(record):
    with pytest.raises(HeaderError, match="conflicts"):
        nest(record)


@pytest.mark.parametrize(
    "header,message",
    [(["id", "", "x"], "blank column name at position\\(s\\): 2"), (["a", "b", "a"], "duplicate column name\\(s\\): a")],
)
def test_bad_headers_rejected(header, message):
    with pytest.raises(HeaderError, match=message):
        rows_to_records([header, ["1", "2", "3"]])


def test_extra_cells_rejected_with_row_number():
    with pytest.raises(HeaderError, match="row 3 has 3 cells but the header has 2"):
        rows_to_records([["a", "b"], ["1", "2"], ["1", "2", "3"]])


def test_cli_array_from_file_with_bom_and_semicolons(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.json"
    src.write_text("﻿id;city\n1;Breda\n\n2;Gent\n", encoding="utf-8")
    assert main([str(src), "-d", ";", "--types", "-o", str(dst)]) == 0
    assert json.loads(dst.read_text(encoding="utf-8")) == [{"id": 1, "city": "Breda"}, {"id": 2, "city": "Gent"}]


def test_cli_lines_from_stdin_nested(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('id,user.name,user.tags\n1,Zoë,"a, b"\n'))
    assert main(["-", "--lines", "--nest"]) == 0
    assert capsys.readouterr().out == '{"id": "1", "user": {"name": "Zoë", "tags": "a, b"}}\n'


def test_cli_compact_output(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a\n1\n"))
    assert main(["-", "--indent", "0"]) == 0
    assert capsys.readouterr().out == '[{"a": "1"}]\n'


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv")]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty)]) == 1
    dup = tmp_path / "dup.csv"
    dup.write_text("a,a\n1,2\n", encoding="utf-8")
    assert main([str(dup)]) == 2
    err = capsys.readouterr().err
    assert "no such file" in err and "no header row" in err and "duplicate column name(s): a" in err

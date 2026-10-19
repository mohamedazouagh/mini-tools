import io

import pytest

from minitools.csvcheck import check_rows, main, parse_rule

HEADER = ["id", "email", "amount", "date"]


def _rows(*rows):
    return [(i + 2, list(r)) for i, r in enumerate(rows)]


def test_parse_rule_accepts_known_rules_and_colons_in_names():
    assert parse_rule("amount:Number") == ("amount", "number")
    assert parse_rule("time:of:day:required") == ("time:of:day", "required")
    with pytest.raises(ValueError, match="unknown rule 'float'"):
        parse_rule("amount:float")
    with pytest.raises(ValueError, match="use column:rule"):
        parse_rule("amount")


def test_type_rules_and_empty_cells_only_fail_required():
    rows = _rows(
        ["1", "a@b.nl", "3.5", "2026-02-28"],
        ["x", "nope", "nan", "2026-02-30"],
        ["", "", "", ""],
        ["-7", "c@d.com", "1_000", "2026-2-1"],
    )
    rules = [("id", "int"), ("email", "email"), ("amount", "number"), ("date", "date"), ("id", "required")]
    assert check_rows(HEADER, rows, rules) == [
        (3, "id", "'x' is not a whole number"),
        (3, "email", "'nope' is not an email address"),
        (3, "amount", "'nan' is not a number"),
        (3, "date", "'2026-02-30' is not a valid YYYY-MM-DD date"),
        (4, "id", "empty"),
        (5, "amount", "'1_000' is not a number"),
        (5, "date", "'2026-2-1' is not a valid YYYY-MM-DD date"),
    ]


def test_unique_points_to_first_use_and_trims_and_ignores_blanks():
    rows = _rows(["1"], [" 1 "], [""], [""], ["2"], ["1"])
    assert check_rows(["id"], rows, [("id", "unique")]) == [
        (3, "id", "'1' already used on line 2"),
        (7, "id", "'1' already used on line 2"),
    ]


def test_short_rows_count_as_empty():
    assert check_rows(HEADER, _rows(["1"]), [("date", "required")]) == [(2, "date", "empty")]


def test_unknown_column_lists_headers():
    with pytest.raises(ValueError, match="unknown column\\(s\\): price; available: id, email, amount, date"):
        check_rows(HEADER, [], [("price", "number")])


def test_cli_ok_and_problems_with_line_numbers(tmp_path, capsys):
    src = tmp_path / "orders.csv"
    src.write_text('﻿id;note;amount\n1;"two\nlines";9.5\n\n1;x;abc\n', encoding="utf-8")
    assert main([str(src), "-d", ";", "-r", "id:unique", "-r", "amount:number"]) == 1
    out = capsys.readouterr()
    assert out.out == "line 5: id: '1' already used on line 2\nline 5: amount: 'abc' is not a number\n"
    assert "2 problem(s) in 1 of 2 row(s)" in out.err
    assert main([str(src), "-d", ";", "-r", "note:required"]) == 0
    assert "ok: 2 row(s) passed 1 rule(s)" in capsys.readouterr().err


def test_cli_max_errors_and_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("n\na\nb\nc\n"))
    assert main(["-", "-r", "n:int", "--max-errors", "1"]) == 1
    assert capsys.readouterr().out == "line 2: n: 'a' is not a whole number\n... and 2 more\n"


def test_cli_bad_input(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    assert main([str(src), "-r", "b:int"]) == 2
    assert "unknown column(s): b" in capsys.readouterr().err
    assert main([str(tmp_path / "missing.csv"), "-r", "a:int"]) == 2
    latin = tmp_path / "latin.csv"
    latin.write_bytes("a\ncaf\xe9\n".encode("cp1252"))
    assert main([str(latin), "-r", "a:required"]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([str(src), "-r", "a:float"])

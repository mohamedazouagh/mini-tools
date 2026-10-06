import pytest

from minitools.csvjoin import join_rows, main

ORDERS_H = ["order", "cust", "amount"]
ORDERS = [["o1", "c1", "10"], ["o2", "c2", "5"], ["o3", "c9", "7"], ["o4", " c1 ", "3"]]
CUST_H = ["cust", "name", "amount"]
CUST = [["c1", "Ada", "x"], ["c2", "Bo", "y"]]


def test_inner_join_trims_keys_and_suffixes_clashing_columns():
    header, rows, unmatched = join_rows(ORDERS_H, ORDERS, CUST_H, CUST, "cust", "cust")
    assert header == ["order", "cust", "amount", "name", "amount_right"]
    assert rows == [
        ["o1", "c1", "10", "Ada", "x"],
        ["o2", "c2", "5", "Bo", "y"],
        ["o4", " c1 ", "3", "Ada", "x"],
    ]
    assert unmatched == 1


def test_left_join_keeps_unmatched_rows_with_empty_right_columns():
    _, rows, unmatched = join_rows(ORDERS_H, ORDERS, CUST_H, CUST, "cust", "cust", how="left")
    assert rows[2] == ["o3", "c9", "7", "", ""]
    assert len(rows) == 4 and unmatched == 1


def test_one_to_many_follows_right_order_and_pads_short_rows():
    _, rows, _ = join_rows(["id"], [["1"]], ["id", "tag"], [["1", "a"], ["2", "b"], ["1"]], "id", "id")
    assert rows == [["1", "a"], ["1", ""]]


def test_different_key_names_and_errors():
    header, rows, _ = join_rows(["id"], [["7"]], ["ID", "v"], [["7", "ok"]], "id", "ID")
    assert header == ["id", "v"] and rows == [["7", "ok"]]
    with pytest.raises(KeyError):
        join_rows(["id"], [], ["x"], [], "id", "id")
    with pytest.raises(ValueError):
        join_rows(["id"], [], ["id"], [], "id", "id", how="outer")


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_writes_output_and_refuses_overwrite(tmp_path, capsys):
    left = _write(tmp_path / "l.csv", "﻿id;qty\n1;2\n\n2;5\n")
    right = _write(tmp_path / "r.csv", "id;name\n1;pen\n")
    out = tmp_path / "out.csv"
    assert main([left, right, "-k", "id", "-d", ";", "--how", "left", "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "id;qty;name\n1;2;pen\n2;5;\n"
    assert "1 left rows without a match" in capsys.readouterr().err
    assert main([left, right, "-k", "id", "-d", ";", "-o", str(out)]) == 1
    assert main([left, right, "-k", "id", "-d", ";", "-o", str(out), "--force"]) == 0
    assert out.read_text(encoding="utf-8") == "id;qty;name\n1;2;pen\n"


def test_cli_reports_missing_file_and_column(tmp_path, capsys):
    left = _write(tmp_path / "l.csv", "id\n1\n")
    assert main([left, str(tmp_path / "nope.csv"), "-k", "id"]) == 1
    assert "no such file" in capsys.readouterr().err
    assert main([left, left, "-k", "sku"]) == 1
    assert "no column 'sku'" in capsys.readouterr().err


def test_cli_stdout(tmp_path, capsys):
    left = _write(tmp_path / "l.csv", "id,a\n1,x\n")
    right = _write(tmp_path / "r.csv", "id,b\n1,y\n")
    assert main([left, right, "-k", "id"]) == 0
    assert capsys.readouterr().out == "id,a,b\n1,x,y\n"

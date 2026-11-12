from decimal import Decimal

import pytest

from minitools.csvbin import BinError, bin_index, bin_rows, main, make_labels, parse_edges

EDGES = [Decimal(0), Decimal(18), Decimal(65)]


@pytest.mark.parametrize("value, expected", [
    ("-1", None), ("0", 0), ("17.99", 0), ("18", 1), ("18.0", 1), ("64.5", 1), ("65", None), ("90", None),
])
def test_bin_index_left_closed(value, expected):
    assert bin_index(Decimal(value), EDGES) == expected


@pytest.mark.parametrize("value, expected", [
    ("0", None), ("0.01", 0), ("18", 0), ("18.01", 1), ("65", 1), ("65.01", None),
])
def test_bin_index_right_closed(value, expected):
    assert bin_index(Decimal(value), EDGES, right=True) == expected


@pytest.mark.parametrize("value, right, expected", [
    ("-5", False, 0), ("0", False, 1), ("65", False, 3), ("0", True, 0), ("65", True, 2), ("66", True, 3),
])
def test_bin_index_open_ends(value, right, expected):
    assert bin_index(Decimal(value), EDGES, right=right, open_ends=True) == expected


def test_labels_keep_edges_as_written():
    _, written = parse_edges(" 0, 18 ,65.5")
    assert make_labels(written) == ["[0, 18)", "[18, 65.5)"]
    assert make_labels(written, right=True, open_ends=True) == ["<= 0", "(0, 18]", "(18, 65.5]", "> 65.5"]
    assert make_labels(written, open_ends=True)[-1] == ">= 65.5"


@pytest.mark.parametrize("text", ["5", "0,0", "10,5", "0,abc,10", "", "1,1e3"])
def test_bad_edges(text):
    with pytest.raises(BinError):
        parse_edges(text)


def test_float_noise_lands_above_edge():
    edges, _ = parse_edges("0,0.3,1")
    assert bin_index(Decimal("0.30000000000000004"), edges) == 1
    assert bin_index(Decimal("0.29999999999999999"), edges) == 0


def test_bin_rows_inserts_after_column_and_reports():
    rows = [(2, ["a", "10", "x"]), (3, ["b", "", "y"]), (4, ["c"]), (5, ["d", "n/a", "z"]), (6, ["e", "70", "w"])]
    labels = make_labels(["0", "18", "65"])
    out, problems, counts = bin_rows(rows, 1, EDGES, labels)
    assert out == [
        ["a", "10", "[0, 18)", "x"],
        ["b", "", "", "y"],
        ["c", "", ""],
        ["d", "n/a", "", "z"],
        ["e", "70", "", "w"],
    ]
    assert problems == [(5, "n/a", "not a plain number"), (6, "70", "outside the edges")]
    assert counts == {"[0, 18)": 1}


def test_cli_labels_open_ends_and_stats(tmp_path, capsys):
    src = tmp_path / "orders.csv"
    src.write_text("id,amount\n1,-5\n2,49.99\n3,50\n4,250\n5,\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    code = main([str(src), "-c", "amount", "--edges", "0,50,250", "--open-ends",
                 "--labels", "refund,small,medium,large", "--into", "size", "--stats", "-o", str(out)])
    assert code == 0
    assert out.read_text(encoding="utf-8").splitlines() == [
        "id,amount,size", "1,-5,refund", "2,49.99,small", "3,50,medium", "4,250,large", "5,,",
    ]
    assert "medium\t1" in capsys.readouterr().err


def test_cli_strict_writes_nothing(tmp_path, capsys):
    src = tmp_path / "people.csv"
    src.write_text("name,age\nA,30\nB,old\nC,99\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    assert main([str(src), "-c", "age", "--edges", "0,18,65", "--strict", "-o", str(out)]) == 1
    assert not out.exists()
    err = capsys.readouterr().err
    assert "line 3, age: not a plain number 'old'" in err
    assert "line 4, age: outside the edges '99'" in err


@pytest.mark.parametrize("args, message", [
    (["-c", "nope", "--edges", "0,1"], "unknown column"),
    (["-c", "age", "--edges", "0,1", "--into", "name"], "already exists"),
    (["-c", "age", "--edges", "0,18,65", "--labels", "kid"], "1 name(s) but there are 2 bins"),
    (["-c", "age", "--edges", "5,1"], "strictly increasing"),
])
def test_cli_rejects_bad_input(tmp_path, capsys, args, message):
    src = tmp_path / "people.csv"
    src.write_text("name,age\nA,30\n", encoding="utf-8")
    assert main([str(src), *args]) == 2
    assert message in capsys.readouterr().err


def test_cli_refuses_to_overwrite_input(tmp_path):
    src = tmp_path / "people.csv"
    src.write_text("name,age\nA,30\n", encoding="utf-8")
    assert main([str(src), "-c", "age", "--edges", "0,18", "-o", str(src)]) == 2

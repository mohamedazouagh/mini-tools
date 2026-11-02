import io

import pytest

from minitools.csvtranspose import main, transpose


def test_transpose_square_and_rectangular():
    assert transpose([["a", "b"], ["1", "2"]]) == [["a", "1"], ["b", "2"]]
    rows = [["metric", "jan", "feb", "mar"], ["sales", "10", "12", "9"], ["visits", "100", "90", "130"]]
    assert transpose(rows) == [
        ["metric", "sales", "visits"],
        ["jan", "10", "100"],
        ["feb", "12", "90"],
        ["mar", "9", "130"],
    ]


def test_transpose_twice_is_identity_for_full_rows():
    rows = [["a", "b", "c"], ["1", "2", "3"]]
    assert transpose(transpose(rows)) == rows


def test_short_rows_are_padded_so_values_stay_in_place():
    rows = [["name", "a", "b", "c"], ["x", "1"], ["y", "2", "3", "4"]]
    assert transpose(rows) == [["name", "x", "y"], ["a", "1", "2"], ["b", "", "3"], ["c", "", "4"]]
    assert transpose([["k", "v"], ["only"]]) == [["k", "only"], ["v"]]
    assert transpose([["k", "v"], ["only"]], keep_trailing=True) == [["k", "only"], ["v", ""]]


def test_blank_lines_and_empty_input():
    assert transpose([]) == []
    assert transpose([[], ["a", "b"], []]) == [["a"], ["b"]]


def test_cli_quoted_cells_and_delimiters(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text('key;value\n"city; region";"Breda\nNL"\n', encoding="utf-8")
    assert main([str(src), "-d", ";", "--out-delimiter", ",", "-o", str(dst)]) == 0
    # the ; no longer needs quotes with a comma delimiter, the line break still does
    assert dst.read_text(encoding="utf-8") == 'key,city; region\nvalue,"Breda\nNL"\n'


def test_cli_stdin_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a,b\n1,2\n"))
    assert main(["-"]) == 0
    assert capsys.readouterr().out == "a,1\nb,2\n"


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv")]) == 1
    assert "no such file" in capsys.readouterr().err
    src = tmp_path / "in.csv"
    src.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    assert main([str(src), "--max-cells", "5"]) == 2
    assert "6 cells is more than --max-cells 5" in capsys.readouterr().err
    assert main([str(src), "-o", str(src)]) == 2
    assert "refusing to write over the input" in capsys.readouterr().err
    assert src.read_text(encoding="utf-8") == "a,b,c\n1,2,3\n"
    bad = tmp_path / "legacy.csv"
    bad.write_bytes("caf\xe9,x\n".encode("latin-1"))
    assert main([str(bad)]) == 1
    assert "not valid UTF-8 (byte 0xe9" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        main([str(src), "-d", ";;"])
    assert exc.value.code == 2


def test_cli_reads_utf8_bom_and_tab(tmp_path, capsys):
    src = tmp_path / "in.tsv"
    src.write_bytes("﻿name\tvalue\nx\t1\n".encode("utf-8"))
    assert main([str(src), "-d", "\\t"]) == 0
    assert capsys.readouterr().out == "name\tx\nvalue\t1\n"

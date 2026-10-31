import io

import pytest

from minitools.csvconvert import convert, detect_delimiter, main


def test_detect_semicolon_even_with_commas_in_cells():
    text = "id;amount;note\n1;12,50;a, b\n2;3,00;c\n"
    assert detect_delimiter(text) == ";"


def test_detect_tab_pipe_and_comma():
    assert detect_delimiter("a\tb\tc\n1\t2\t3\n") == "\t"
    assert detect_delimiter("a|b\n1|2\n") == "|"
    assert detect_delimiter('a,b\n"x;y",2\n') == ","


def test_detect_survives_one_ragged_row():
    assert detect_delimiter("a;b;c\n1;2,5;x\n2;3\n4;5;6\n") == ";"


def test_detect_fails_without_a_consistent_split():
    with pytest.raises(ValueError, match="pass it with -d"):
        detect_delimiter("just one column\nhello\n")
    with pytest.raises(ValueError):
        detect_delimiter("a,b\n1,2,3\n4\n")


def test_convert_keeps_quoted_cells_and_reports_ragged_rows():
    text = 'id;note;city\n1;"line one\nline two";Breda\n\n2;x\n3;"a;b";"say ""hi"""\n'
    out, ragged, rows, cols = convert(text, ";", ",")
    assert out == 'id,note,city\n1,"line one\nline two",Breda\n2,x\n3,a;b,"say ""hi"""\n'
    assert ragged == [(5, 2)]  # row "2;x" starts on line 5 (after the 2-line cell and a blank line)
    assert (rows, cols) == (3, 3)


def test_convert_crlf():
    out, *_ = convert("a,b\n1,2\n", ",", ";", "\r\n")
    assert out == "a;b\r\n1;2\r\n"


def test_cli_cp1252_semicolons_to_utf8_commas(tmp_path, capsys):
    src, dst = tmp_path / "export.csv", tmp_path / "clean.csv"
    src.write_bytes("naam;stad;bedrag\r\nZoë;Café Noord;1,50\r\n".encode("cp1252"))
    assert main([str(src), "--encoding", "cp1252", "--info", "-o", str(dst)]) == 0
    assert dst.read_bytes() == "naam,stad,bedrag\nZoë,Café Noord,\"1,50\"\n".encode("utf-8")
    assert "delimiter ';' -> ',', 1 rows, 3 columns, encoding cp1252 -> utf-8" in capsys.readouterr().err


def test_cli_for_excel_bom_crlf_semicolons(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "excel.csv"
    src.write_text("\ufeffa,b\n1,\"x;y\"\n", encoding="utf-8")
    assert main([str(src), "--to", "semicolon", "--bom", "--crlf", "-o", str(dst)]) == 0
    assert dst.read_bytes() == b'\xef\xbb\xbfa;b\r\n1;"x;y"\r\n'


def test_cli_stdin_tab_to_comma(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("a\tb\n1\t2\n"))
    assert main(["-", "-d", "tab"]) == 0
    assert capsys.readouterr().out == "a,b\n1,2\n"


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv")]) == 1
    single = tmp_path / "single.csv"
    single.write_text("name\nAna\n", encoding="utf-8")
    assert main([str(single)]) == 2
    assert main([str(single), "-o", str(single)]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_bytes("a,b\n1,Zoë\n".encode("cp1252"))
    assert main([str(bad)]) == 1
    err = capsys.readouterr().err
    assert "no such file" in err and "could not detect the delimiter" in err
    assert "refusing to write over the input" in err and "is not valid utf-8" in err
    assert single.read_text(encoding="utf-8") == "name\nAna\n"


def test_cli_rejects_bad_delimiter_and_encoding(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("a,b\n1,2\n", encoding="utf-8")
    for extra in (["--to", ";;"], ["-d", "ab"], ["--encoding", "nope-42"]):
        with pytest.raises(SystemExit) as exc:
            main([str(src), *extra])
        assert exc.value.code == 2

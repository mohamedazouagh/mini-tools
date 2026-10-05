import io

import pytest

from minitools.wordfreq import analyse, main, words


def test_words_rule():
    text = "Café in Breda's centre; e-mail me_now, 2026 rocks!"
    assert words(text) == ["café", "in", "breda's", "centre", "e-mail", "me", "now", "2026", "rocks"]


def test_analyse_counts_and_filters():
    text = "The rain in Breda.\nThe rain stopped.\n"
    s = analyse(text)
    assert (s.lines, s.words, s.chars) == (2, 7, len(text))
    assert s.counts.most_common(2) == [("the", 2), ("rain", 2)]
    filtered = analyse(text, min_length=4, stopwords=frozenset({"rain"}))
    assert filtered.words == 7  # totals are unaffected by filters
    assert dict(filtered.counts) == {"breda": 1, "stopped": 1}


def test_cli_multiple_files_and_stopwords(tmp_path, capsys):
    a, b, stop = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "stop.txt"
    a.write_text("data data pipeline\n", encoding="utf-8")
    b.write_text("the data\n", encoding="utf-8")
    stop.write_text("the\n", encoding="utf-8")
    assert main([str(a), str(b), "--stopwords", str(stop), "-n", "2"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "lines 2  words 5  chars 28  unique 2"
    assert out[1:] == ["data      3", "pipeline  1"]


def test_cli_csv_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("b a b"))
    assert main(["-", "--csv"]) == 0
    assert capsys.readouterr().out == "word,count\nb,2\na,1\n"


def test_cli_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.txt")]) == 1
    assert "no such file" in capsys.readouterr().err


def test_cli_non_utf8_file_gives_clear_error_and_encoding_flag_reads_it(tmp_path, capsys):
    src = tmp_path / "old.txt"
    src.write_bytes("café café crème\n".encode("cp1252"))
    assert main([str(src)]) == 1
    err = capsys.readouterr().err
    assert "is not valid utf-8" in err and "byte 0xe9" in err and "--encoding" in err
    assert main([str(src), "--encoding", "cp1252", "-n", "1"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("lines 1  words 3")
    assert out[1].split() == ["café", "2"]


def test_cli_unknown_encoding_is_rejected(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(SystemExit):
        main([str(src), "--encoding", "no-such-codec"])


import io

from minitools.dedupe import dedupe_lines, main


def test_keeps_first_occurrence_in_order():
    assert list(dedupe_lines(["b", "a", "b", "c", "a"])) == ["b", "a", "c"]


def test_case_and_whitespace_options_only_affect_comparison():
    lines = ["Breda", " breda ", "Tilburg", "BREDA"]
    assert list(dedupe_lines(lines)) == lines
    assert list(dedupe_lines(lines, ignore_case=True)) == ["Breda", " breda ", "Tilburg"]
    assert list(dedupe_lines(lines, ignore_case=True, strip=True)) == ["Breda", "Tilburg"]


def test_blank_lines():
    lines = ["a", "", "b", "  ", ""]
    assert list(dedupe_lines(lines)) == ["a", "", "b", "  "]
    assert list(dedupe_lines(lines, skip_blank=True)) == ["a", "b"]


def test_cli_file_to_file_with_stats(tmp_path, capsys):
    src, dst = tmp_path / "in.txt", tmp_path / "out.txt"
    src.write_text("x\ny\nx\nY\n", encoding="utf-8")
    assert main([str(src), "-o", str(dst), "-i", "--stats"]) == 0
    assert dst.read_text(encoding="utf-8") == "x\ny\n"
    assert "kept 2 of 4 lines, dropped 2" in capsys.readouterr().err


def test_cli_stdin_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("one\r\ntwo\r\none\r\n"))
    assert main(["-"]) == 0
    assert capsys.readouterr().out == "one\ntwo\n"


def test_cli_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.txt")]) == 1
    assert "no such file" in capsys.readouterr().err


def test_keep_last_keeps_final_occurrence_at_its_position():
    assert list(dedupe_lines(["b", "a", "b", "c", "a"], keep_last=True)) == ["b", "c", "a"]


def test_keep_last_combines_with_other_options():
    lines = ["Breda", "", "Tilburg", " BREDA ", ""]
    assert list(dedupe_lines(lines, ignore_case=True, strip=True, skip_blank=True, keep_last=True)) == [
        "Tilburg",
        " BREDA ",
    ]


def test_cli_keep_last(tmp_path):
    src, dst = tmp_path / "in.txt", tmp_path / "out.txt"
    src.write_text("id1 old\nid2\nid1 old\n", encoding="utf-8")
    assert main([str(src), "-o", str(dst), "--keep-last"]) == 0
    assert dst.read_text(encoding="utf-8") == "id2\nid1 old\n"

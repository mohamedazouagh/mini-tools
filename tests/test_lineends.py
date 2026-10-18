import pytest

from minitools.lineends import BOM, convert, inspect, main


def test_inspect_counts_each_ending_and_style():
    rep = inspect(b"a\r\nb\nc\rd\r\n")
    assert (rep.lf, rep.crlf, rep.cr) == (1, 2, 1)
    assert rep.style == "mixed" and rep.final_newline
    assert inspect(b"a\nb\n").style == "LF"
    assert inspect(b"a\r\nb").style == "CRLF"
    assert inspect(b"no newline").style == "none"
    assert inspect(BOM + b"x\n").bom


def test_convert_all_styles_and_bom():
    assert convert(b"a\r\nb\rc\nd", "lf") == b"a\nb\nc\nd"
    assert convert(b"a\r\nb\rc\nd", "crlf") == b"a\r\nb\r\nc\r\nd"
    assert convert(b"a\r\n", "crlf") == b"a\r\n"  # no doubled CR
    assert convert(BOM + b"x\n", strip_bom=True) == b"x\n"
    assert convert(BOM + b"x\n") == BOM + b"x\n"
    with pytest.raises(ValueError):
        convert(b"x", "cr")


def test_report_lists_files_in_folder_with_glob(tmp_path, capsys):
    (tmp_path / "a.csv").write_bytes(b"h\r\n1\r\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.csv").write_bytes(BOM + b"h\n1")
    (tmp_path / "c.txt").write_bytes(b"x\n")
    assert main([str(tmp_path), "--glob", "*.csv"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2
    assert out[0].startswith("CRLF  lf=0 crlf=2 cr=0  bom=no  final-newline=yes")
    assert out[1].startswith("LF    lf=1 crlf=0 cr=0  bom=yes  final-newline=no")


def test_dry_run_changes_nothing_and_apply_writes(tmp_path, capsys):
    f = tmp_path / "x.csv"
    f.write_bytes(BOM + b"h\r\n1\r\n")
    assert main([str(f), "--to", "lf", "--strip-bom"]) == 0
    assert f.read_bytes() == BOM + b"h\r\n1\r\n"
    assert "would fix" in capsys.readouterr().out
    assert main([str(f), "--to", "lf", "--strip-bom", "--apply"]) == 0
    assert f.read_bytes() == b"h\n1\n"


def test_check_exit_codes(tmp_path, capsys):
    good, bad = tmp_path / "good.txt", tmp_path / "bad.txt"
    good.write_bytes(b"a\nb\n")
    bad.write_bytes(b"a\r\nb\n")
    assert main([str(good), "--check", "lf"]) == 0
    assert main([str(good), str(bad), "--check", "lf"]) == 1
    assert f"{bad}: mixed" in capsys.readouterr().out


def test_binary_files_are_skipped(tmp_path, capsys):
    f = tmp_path / "img.bin"
    f.write_bytes(b"\x89PNG\r\n\x00\x00\r\n")
    assert main([str(f), "--to", "lf", "--apply"]) == 0
    assert f.read_bytes() == b"\x89PNG\r\n\x00\x00\r\n"
    assert "skipped binary" in capsys.readouterr().err


def test_missing_path_and_bad_flag_combinations(tmp_path, capsys):
    assert main([str(tmp_path / "nope.txt")]) == 2
    assert "no such file" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([str(tmp_path), "--apply"])
    with pytest.raises(SystemExit):
        main([str(tmp_path), "--check", "lf", "--to", "lf"])

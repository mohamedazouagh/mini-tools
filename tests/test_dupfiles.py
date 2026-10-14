import argparse

import pytest

from minitools.dupfiles import find_duplicates, human, main, parse_size


def _tree(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)


def test_groups_identical_content_not_just_same_size(tmp_path):
    _tree(tmp_path, {"a.txt": b"hello", "sub/b.txt": b"hello", "c.txt": b"world", "d.txt": b"other!"})
    groups = find_duplicates(sorted(tmp_path.rglob("*.txt")))
    assert groups == [(5, [tmp_path / "a.txt", tmp_path / "sub" / "b.txt"])]


def test_empty_files_skipped_unless_included(tmp_path):
    _tree(tmp_path, {"e1": b"", "e2": b""})
    files = list(tmp_path.iterdir())
    assert find_duplicates(files) == []
    assert find_duplicates(files, include_empty=True) == [(0, sorted(files))]


def test_min_size_and_largest_group_first(tmp_path):
    _tree(tmp_path, {"s1": b"ab", "s2": b"ab", "b1": b"x" * 100, "b2": b"x" * 100})
    files = list(tmp_path.iterdir())
    assert [size for size, _ in find_duplicates(files)] == [100, 2]
    assert [size for size, _ in find_duplicates(files, min_size=50)] == [100]


@pytest.mark.parametrize("text,expected", [("500", 500), ("64K", 65536), ("1.5m", 1572864), ("2GB", 2 * 1024**3), ("0", 0)])
def test_parse_size(text, expected):
    assert parse_size(text) == expected


@pytest.mark.parametrize("text", ["abc", "", "-1", "1T"])
def test_parse_size_rejects_garbage(text):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_size(text)


def test_human():
    assert human(512) == "512B"
    assert human(2048) == "2.0K"
    assert human(3 * 1024**3) == "3.0G"


def test_cli_text_output_and_exit_codes(tmp_path, capsys):
    _tree(tmp_path, {"x/a.bin": b"123", "y/a.bin": b"123", "z.bin": b"999"})
    assert main([str(tmp_path)]) == 1
    out, err = capsys.readouterr()
    assert out.splitlines() == ["2 x 3B", "  x/a.bin", "  y/a.bin"]
    assert "3 file(s) scanned, 1 duplicate group(s), 3B reclaimable" in err

    assert main([str(tmp_path), "--no-recursive"]) == 0


def test_cli_csv_and_glob(tmp_path, capsys):
    _tree(tmp_path, {"a.pdf": b"same", "b.pdf": b"same", "a.txt": b"same"})
    assert main([str(tmp_path), "--glob", "*.pdf", "--csv"]) == 1
    out, _ = capsys.readouterr()
    assert out.splitlines() == ["group,size,path", "1,4,a.pdf", "1,4,b.pdf"]


def test_cli_missing_folder(tmp_path, capsys):
    assert main([str(tmp_path / "nope")]) == 2
    assert "no such folder" in capsys.readouterr().err


def test_cli_does_not_modify_files(tmp_path):
    _tree(tmp_path, {"a": b"dup", "b": b"dup"})
    main([str(tmp_path)])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a", "b"]

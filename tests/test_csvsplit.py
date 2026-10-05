import pytest

from minitools.csvsplit import chunk_rows, group_rows, main, safe_name


def test_chunk_rows_sizes_and_order():
    rows = [[str(i)] for i in range(7)]
    chunks = list(chunk_rows(rows, 3))
    assert [len(c) for c in chunks] == [3, 3, 1]
    assert [r[0] for c in chunks for r in c] == [str(i) for i in range(7)]
    assert list(chunk_rows([], 3)) == []
    with pytest.raises(ValueError):
        list(chunk_rows(rows, 0))


@pytest.mark.parametrize(
    "value,expected",
    [("NL", "NL"), ("  New York ", "New_York"), ("a/b:c", "a_b_c"), ("", "empty"), ("...", "empty"), ("São Paulo", "São_Paulo")],
)
def test_safe_name(value, expected):
    assert safe_name(value) == expected


def test_group_rows_keeps_first_seen_order_and_handles_short_rows():
    rows = [["1", "BE"], ["2", "NL"], ["3", "BE"], ["4"]]
    groups = group_rows(rows, 1)
    assert list(groups) == ["BE", "NL", "empty"]
    assert groups["BE"] == [["1", "BE"], ["3", "BE"]]


def _csv(tmp_path, text, name="sales.csv"):
    src = tmp_path / name
    src.write_text(text, encoding="utf-8")
    return src


def test_cli_rows_mode_repeats_header_and_skips_blank_lines(tmp_path):
    src = _csv(tmp_path, "id,country\n1,NL\n2,BE\n\n3,NL\n4,DE\n5,NL\n")
    out = tmp_path / "parts"
    assert main([str(src), "--rows", "2", "-o", str(out)]) == 0
    files = sorted(p.name for p in out.iterdir())
    assert files == ["sales_001.csv", "sales_002.csv", "sales_003.csv"]
    assert (out / "sales_001.csv").read_text(encoding="utf-8") == "id,country\n1,NL\n2,BE\n"
    assert (out / "sales_003.csv").read_text(encoding="utf-8") == "id,country\n5,NL\n"


def test_cli_by_column_with_delimiter(tmp_path, capsys):
    src = _csv(tmp_path, "id;country\n1;NL\n2;BE\n3;NL\n4;\n")
    assert main([str(src), "--by", "country", "-d", ";"]) == 0
    assert (tmp_path / "sales_NL.csv").read_text(encoding="utf-8") == "id;country\n1;NL\n3;NL\n"
    assert (tmp_path / "sales_empty.csv").read_text(encoding="utf-8") == "id;country\n4;\n"
    assert "4 rows -> 3 files" in capsys.readouterr().out


def test_cli_refuses_to_overwrite_without_force(tmp_path, capsys):
    src = _csv(tmp_path, "id,country\n1,NL\n")
    existing = tmp_path / "sales_NL.csv"
    existing.write_text("keep me", encoding="utf-8")
    assert main([str(src), "--by", "country"]) == 1
    assert "already exist" in capsys.readouterr().err
    assert existing.read_text(encoding="utf-8") == "keep me"
    assert main([str(src), "--by", "country", "--force"]) == 0
    assert existing.read_text(encoding="utf-8") == "id,country\n1,NL\n"


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv"), "--rows", "5"]) == 1
    assert "no such file" in capsys.readouterr().err
    src = _csv(tmp_path, "id,country\n1,NL\n")
    assert main([str(src), "--by", "city"]) == 1
    assert "columns are: id, country" in capsys.readouterr().err
    empty = _csv(tmp_path, "", name="empty.csv")
    assert main([str(empty), "--rows", "5"]) == 1
    assert "no header row" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main([str(src), "--rows", "0"])

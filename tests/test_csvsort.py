import io

from minitools.csvsort import main, sort_rows

HEADER = ["name", "country", "amount"]
ROWS = [
    ["ana", "NL", "10"],
    ["bo", "be", "9"],
    ["cem", "NL", ""],
    ["dee", "BE", "100"],
    ["eli", "NL", "2.5"],
]


def names(rows):
    return [r[0] for r in rows]


def test_numeric_column_sorts_as_numbers_with_empty_last():
    assert names(sort_rows(HEADER, ROWS, ["amount"])) == ["eli", "bo", "ana", "dee", "cem"]
    assert names(sort_rows(HEADER, ROWS, ["amount"], reverse=True)) == ["dee", "ana", "bo", "eli", "cem"]


def test_multiple_keys_text_is_case_insensitive_and_stable():
    out = sort_rows(HEADER, ROWS, ["country", "amount"])
    assert names(out) == ["bo", "dee", "eli", "ana", "cem"]


def test_mixed_column_falls_back_to_text():
    rows = [["a", "x", "10"], ["b", "x", "n/a"], ["c", "x", "9"]]
    assert names(sort_rows(HEADER, rows, ["amount"])) == ["a", "c", "b"]


def test_short_rows_are_padded():
    out = sort_rows(HEADER, [["z", "NL"], ["y", "NL", "1"]], ["amount"])
    assert out == [["y", "NL", "1"], ["z", "NL", ""]]


def test_cli_stdin_semicolon_and_output_file(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("name;amount\nb;20\na;3\n"))
    dest = tmp_path / "out.csv"
    assert main(["-", "-k", "amount", "-d", ";", "-o", str(dest)]) == 0
    assert dest.read_text(encoding="utf-8") == "name;amount\na;3\nb;20\n"


def test_cli_unknown_column_lists_headers(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("name,amount\na,1\n", encoding="utf-8")
    assert main([str(src), "-k", "price"]) == 1
    err = capsys.readouterr().err
    assert "unknown column(s): price" in err and "available: name, amount" in err


def test_cli_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv"), "-k", "a"]) == 1
    assert "no such file" in capsys.readouterr().err


def test_cli_keeps_line_breaks_inside_quoted_cells(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_bytes(b'id,note\r\n2,"line one\r\nline two"\r\n1,plain\r\n')
    assert main([str(src), "-k", "id"]) == 0
    assert capsys.readouterr().out == 'id,note\n1,plain\n2,"line one\nline two"\n'


def test_cli_multiline_cell_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('k,v\nb,"x\ny"\na,z\n'))
    assert main(["-", "-k", "k"]) == 0
    assert capsys.readouterr().out == 'k,v\na,z\nb,"x\ny"\n'


def test_per_key_direction():
    # country A-Z, then amount high to low inside each country; empty amount still last
    out = sort_rows(HEADER, ROWS, ["country", "amount:desc"])
    assert names(out) == ["dee", "bo", "ana", "eli", "cem"]
    assert names(sort_rows(HEADER, ROWS, ["amount:asc"])) == names(sort_rows(HEADER, ROWS, ["amount"]))
    assert names(sort_rows(HEADER, ROWS, ["amount:DESC"])) == ["dee", "ana", "bo", "eli", "cem"]


def test_reverse_flips_per_key_directions():
    out = sort_rows(HEADER, ROWS, ["country", "amount:desc"], reverse=True)
    assert names(out) == ["eli", "ana", "cem", "bo", "dee"]  # country Z-A, amount low to high, empty last


def test_header_containing_desc_suffix_stays_reachable():
    header = ["id", "rank:desc"]
    rows = [["a", "2"], ["b", "1"]]
    assert names(sort_rows(header, rows, ["rank:desc"])) == ["b", "a"]  # the column, ascending
    try:
        sort_rows(HEADER, ROWS, ["price:desc"])
    except KeyError as exc:
        assert "unknown column(s): price" in exc.args[0]
    else:
        raise AssertionError("expected KeyError")


def test_cli_per_key_direction(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("c,n\nNL,1\nBE,5\nNL,3\nBE,2\n"))
    assert main(["-", "-k", "c,n:desc"]) == 0
    assert capsys.readouterr().out == "c,n\nBE,5\nBE,2\nNL,3\nNL,1\n"

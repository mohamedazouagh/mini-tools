from minitools.csvstats import main, profile


def test_profile_numeric_text_and_empty_cells():
    rows = [
        {"city": "Breda", "temp": "19.5", "note": ""},
        {"city": "Tilburg", "temp": "21", "note": "windy"},
        {"city": "Breda", "temp": " ", "note": "x"},
    ]
    city, temp, note = profile(rows, ["city", "temp", "note"])
    assert city == {"column": "city", "filled": 3, "empty": 0, "distinct": 2, "min": None, "max": None, "mean": None}
    assert temp == {"column": "temp", "filled": 2, "empty": 1, "distinct": 2, "min": 19.5, "max": 21.0, "mean": 20.25}
    assert note["empty"] == 1 and note["min"] is None


def test_mixed_column_is_not_numeric_and_all_empty_column_is_safe():
    rows = [{"a": "1", "b": ""}, {"a": "n/a", "b": ""}]
    a, b = profile(rows, ["a", "b"])
    assert a["mean"] is None
    assert b == {"column": "b", "filled": 0, "empty": 2, "distinct": 0, "min": None, "max": None, "mean": None}


def test_decimal_comma():
    rows = [{"price": "1.234,50"}, {"price": "0,50"}]
    (price,) = profile(rows, ["price"], decimal_comma=True)
    assert (price["min"], price["max"], price["mean"]) == (0.5, 1234.5, 617.5)


def test_short_rows_count_as_empty():
    rows = [{"a": "1", "b": None}]  # csv.DictReader fills missing fields with None
    assert profile(rows, ["a", "b"])[1]["empty"] == 1


def test_cli_table_and_csv(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("name;score\nana;7\nbram;9\n", encoding="utf-8")
    assert main([str(src), "-d", ";"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["column", "filled", "empty", "distinct", "min", "max", "mean"]
    assert out[2].split() == ["score", "2", "0", "2", "7", "9", "8"]
    assert main([str(src), "-d", ";", "--csv"]) == 0
    assert capsys.readouterr().out.splitlines()[1] == "name,2,0,2,,,"


def test_cli_missing_file_and_empty_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv")]) == 1
    assert "no such file" in capsys.readouterr().err
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main([str(empty)]) == 1
    assert "no header row" in capsys.readouterr().err


def test_nan_inf_and_underscore_spellings_are_text_not_numbers():
    rows = [{"name": "Nan", "n": "1_000"}, {"name": "Inf", "n": "2"}]
    by_col = {s["column"]: s for s in profile(rows, ["name", "n"])}
    assert by_col["name"]["mean"] is None and by_col["name"]["min"] is None
    assert by_col["n"]["mean"] is None
    ok = profile([{"x": "1e3"}, {"x": "-2.5"}], ["x"])[0]
    assert (ok["min"], ok["max"]) == (-2.5, 1000.0)


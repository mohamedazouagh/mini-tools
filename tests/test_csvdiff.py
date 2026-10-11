import pytest

from minitools.csvdiff import DiffError, diff_rows, format_diff, main

OLD = [["id", "name", "city"], ["1", "Ana", "Breda"], ["2", "Bo", "Gent"], ["3", "Cem", "Delft"]]


def test_reordering_is_not_a_change():
    d = diff_rows(OLD, [OLD[0], OLD[3], OLD[1], OLD[2]], "id")
    assert d.identical and d.unchanged == 3


def test_added_removed_changed():
    new = [["id", "name", "city"], ["1", "Ana", "Tilburg"], ["3", "Cem ", "Delft"], ["4", "Dee", "Ede"]]
    d = diff_rows(OLD, new, "id")
    assert d.removed == ["2"] and d.added == ["4"]
    assert d.changed == {"1": [("city", "Breda", "Tilburg")]}  # "Cem " is trimmed, so unchanged
    assert d.unchanged == 1
    assert format_diff(d) == (
        "- 2\n+ 4\n~ 1: city: 'Breda' -> 'Tilburg'\nadded 1, removed 1, changed 1, unchanged 1\n"
    )


def test_columns_only_in_one_file_are_reported_not_compared():
    new = [["id", "name", "email"], ["1", "Ana", "a@example.com"], ["2", "Bo", ""], ["3", "Cem", ""]]
    d = diff_rows(OLD, new, "id")
    assert d.columns_added == ["email"] and d.columns_removed == ["city"]
    assert not d.changed and not d.identical
    assert format_diff(d, summary_only=True) == (
        "columns added: email\ncolumns removed: city\nadded 0, removed 0, changed 0, unchanged 3\n"
    )


def test_short_rows_count_as_empty_cells():
    d = diff_rows([["id", "x"], ["1"]], [["id", "x"], ["1", ""]], "id")
    assert d.identical


def test_bad_key_and_duplicates():
    with pytest.raises(DiffError, match="key column 'sku' not in old file; available: id, name, city"):
        diff_rows(OLD, OLD, "sku")
    with pytest.raises(DiffError, match="duplicate key '1' in new file"):
        diff_rows(OLD, OLD + [["1", "Ana2", "x"]], "id")
    with pytest.raises(DiffError, match="old file has no header row"):
        diff_rows([], OLD, "id")


def test_cli_exit_codes(tmp_path, capsys):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("﻿id;qty\n1;5\n2;7\n", encoding="utf-8")
    b.write_text("id;qty\n2;7\n1;6\n", encoding="utf-8")
    assert main([str(a), str(a), "-k", "id", "-d", ";"]) == 0
    capsys.readouterr()
    assert main([str(a), str(b), "-k", "id", "-d", ";"]) == 1
    assert "~ 1: qty: '5' -> '6'" in capsys.readouterr().out
    assert main([str(a), str(tmp_path / "missing.csv"), "-k", "id"]) == 2
    assert "no such file" in capsys.readouterr().err
    assert main([str(a), str(b), "-k", "nope", "-d", ";"]) == 2

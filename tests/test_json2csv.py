import json

import pytest

from minitools.json2csv import flatten, main, to_table


def test_flatten_nested_and_lists():
    obj = {"id": 1, "geo": {"city": "Breda", "pos": {"lat": 51.57}}, "tags": ["a", "b"], "note": None}
    assert flatten(obj) == {"id": 1, "geo.city": "Breda", "geo.pos.lat": 51.57, "tags": '["a", "b"]', "note": ""}


def test_to_table_union_of_keys_in_first_seen_order():
    columns, rows = to_table([{"a": 1, "b": 2}, {"b": 3, "c": 4}])
    assert columns == ["a", "b", "c"]
    assert rows[1] == {"b": 3, "c": 4}


def test_to_table_rejects_non_list():
    with pytest.raises(ValueError):
        to_table({"a": 1})


def test_cli_fills_missing_cells(tmp_path):
    src, dst = tmp_path / "in.json", tmp_path / "out.csv"
    src.write_text(json.dumps([{"a": 1, "b": {"x": 2}}, {"a": 3}]), encoding="utf-8")
    assert main([str(src), str(dst)]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == ["a,b.x", "1,2", "3,"]


def test_cli_bad_json_returns_error(tmp_path, capsys):
    src = tmp_path / "bad.json"
    src.write_text("{not json", encoding="utf-8")
    assert main([str(src), str(tmp_path / "out.csv")]) == 1
    assert "json2csv:" in capsys.readouterr().err


def test_cli_reads_json_lines_by_suffix(tmp_path):
    src, dst = tmp_path / "events.jsonl", tmp_path / "out.csv"
    src.write_text('{"a": 1, "b": {"x": 2}}\n\n{"a": 3}\n', encoding="utf-8")
    assert main([str(src), str(dst)]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == ["a,b.x", "1,2", "3,"]


def test_cli_lines_flag_for_other_suffix(tmp_path):
    src, dst = tmp_path / "events.txt", tmp_path / "out.csv"
    src.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    assert main([str(src), str(dst), "--lines"]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == ["a", "1", "2"]


def test_cli_json_lines_error_names_line(tmp_path, capsys):
    src = tmp_path / "bad.jsonl"
    src.write_text('{"a": 1}\n{oops\n', encoding="utf-8")
    assert main([str(src), str(tmp_path / "out.csv")]) == 1
    assert "line 2" in capsys.readouterr().err

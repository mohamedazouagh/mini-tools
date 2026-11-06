import io

import pytest

from minitools.jsonfmt import JsonFmtError, format_text, main


def test_pretty_print_default_indent_keeps_unicode():
    assert format_text('{"city":"Café","n":[1,2]}') == '{\n  "city": "Café",\n  "n": [\n    1,\n    2\n  ]\n}\n'


def test_compact_sort_keys_and_ascii():
    assert format_text('{"b": 1, "a": {"y": 2, "x": 3}}', indent=None, sort_keys=True) == '{"a":{"x":3,"y":2},"b":1}\n'
    assert format_text('"é"', ascii_only=True) == '"\\u00e9"\n'


def test_invalid_json_reports_line_and_column():
    with pytest.raises(JsonFmtError) as err:
        format_text('{\n  "a": 1,\n  "b": \n}')
    assert (err.value.lineno, err.value.colno) == (4, 1)
    assert str(err.value).startswith("4:1: Expecting value")


def test_nan_and_infinity_rejected():
    for bad in ('{"x": NaN}', "[Infinity]", "-Infinity"):
        with pytest.raises(JsonFmtError, match="not valid JSON"):
            format_text(bad)


def test_duplicate_keys_only_rejected_with_strict_keys():
    assert format_text('{"a": 1, "a": 2}', indent=None) == '{"a":2}\n'
    with pytest.raises(JsonFmtError, match="duplicate key 'a'"):
        format_text('{"a": 1, "a": 2}', strict_keys=True)
    with pytest.raises(JsonFmtError, match="duplicate key"):
        format_text('[{"k": 1}, {"inner": {"z": 1, "z": 1}}]', strict_keys=True)


def test_empty_input():
    with pytest.raises(JsonFmtError, match="empty input"):
        format_text("  \n")
    assert format_text("", lines=True) == ""


def test_json_lines_compact_per_record_and_blank_lines_skipped():
    text = '{"b": 2, "a": 1}\n\n  [1, 2]  \n"x"\n'
    assert format_text(text, lines=True, sort_keys=True) == '{"a":1,"b":2}\n[1,2]\n"x"\n'


def test_json_lines_error_uses_file_line():
    with pytest.raises(JsonFmtError) as err:
        format_text('{"ok": 1}\n\n{"bad": }\n', lines=True)
    assert (err.value.lineno, err.value.colno) == (3, 9)
    with pytest.raises(JsonFmtError, match=r"^2: duplicate key"):
        format_text('{"a": 1}\n{"a": 1, "a": 2}\n', lines=True, strict_keys=True)


def test_cli_file_to_file_with_bom(tmp_path):
    src, dst = tmp_path / "in.json", tmp_path / "out.json"
    src.write_bytes('\ufeff{"b":1,"a":[]}'.encode("utf-8"))
    assert main([str(src), "--sort-keys", "--indent", "4", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == '{\n    "a": [],\n    "b": 1\n}\n'


def test_cli_stdin_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('[1, {"a": null}]'))
    assert main(["-", "--compact"]) == 0
    assert capsys.readouterr().out == '[1,{"a":null}]\n'


def test_cli_check_mode(tmp_path, capsys):
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_bytes(b'{\r\n  "a": 1\r\n}\r\n')  # CRLF line endings don't count as a difference
    bad.write_text('{"a":1}', encoding="utf-8")
    assert main([str(good), "--check"]) == 0
    assert main([str(bad), "--check"]) == 1
    assert "would be reformatted" in capsys.readouterr().err
    assert bad.read_text(encoding="utf-8") == '{"a":1}'  # untouched


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "x.json"
    src.write_text('{"a": tru}', encoding="utf-8")
    assert main([str(src)]) == 2
    err = capsys.readouterr().err
    assert f"{src}:1:7:" in err and "Traceback" not in err
    assert main([str(tmp_path / "missing.json")]) == 1
    src.write_text("{}", encoding="utf-8")
    assert main([str(src), "-o", str(src)]) == 2
    assert "refusing to write over" in capsys.readouterr().err
    (tmp_path / "latin.json").write_bytes(b'"caf\xe9"')
    assert main([str(tmp_path / "latin.json")]) == 2
    assert "not valid UTF-8 (byte 0xe9" in capsys.readouterr().err
    for bad_args in (["--indent", "9"], ["--compact", "--indent", "2"], ["--check", "-o", "y.json"]):
        with pytest.raises(SystemExit) as exc:
            main([str(src), *bad_args])
        assert exc.value.code == 2

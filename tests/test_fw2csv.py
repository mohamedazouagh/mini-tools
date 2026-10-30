import csv
import io

import pytest

from minitools.fw2csv import detect_starts, main, split_line, starts_from_widths

REPORT = (
    "id   first name   city        amount\n"
    "1    Ana de Wit   Breda        12.50\n"
    "\n"
    "22   Bo           Den Haag    100.00\n"
)


def run(capsys, argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(argv)
    out, err = capsys.readouterr()
    return code, list(csv.reader(io.StringIO(out))), err


def test_detect_starts_splits_on_blank_positions():
    lines = [line for line in REPORT.splitlines() if line.strip()]
    assert detect_starts(lines) == [0, 5, 18, 30]  # spaces inside names are covered by other rows
    # a space that is blank on every line splits with the default gap, but not with gap=2
    assert detect_starts(["a b  c", "a b  c"]) == [0, 2, 5]
    assert detect_starts(["a b  c", "a b  c"], gap=2) == [0, 5]
    assert detect_starts([]) == []


def test_split_line_last_column_runs_to_end():
    assert split_line("ab  cd  efgh ij", [0, 4, 8]) == ["ab", "cd", "efgh ij"]
    assert split_line("ab", [0, 4, 8]) == ["ab", "", ""]  # short lines give empty cells
    assert starts_from_widths([5, 13, 12]) == [0, 5, 18]


def test_cli_detects_columns_with_gap_and_skips_blank_lines(tmp_path, capsys):
    src = tmp_path / "r.txt"
    src.write_text(REPORT, encoding="utf-8")
    code, rows, _ = run(capsys, [str(src), "--gap", "2"])
    assert code == 0
    assert rows == [
        ["id", "first name", "city", "amount"],
        ["1", "Ana de Wit", "Breda", "12.50"],
        ["22", "Bo", "Den Haag", "100.00"],
    ]


def test_cli_widths_skip_names_and_tabs(capsys, monkeypatch):
    text = "QUARTERLY REPORT\n\nNL\t2026  7\nBE\t2025 12\n"
    code, rows, _ = run(capsys, ["-", "-w", "8,5,1", "--skip", "1", "--names", "country,year,n"], text, monkeypatch)
    assert code == 0
    assert rows == [["country", "year", "n"], ["NL", "2026", "7"], ["BE", "2025", "12"]]


def test_cli_semicolon_output_file(tmp_path, capsys):
    src, dst = tmp_path / "r.txt", tmp_path / "out.csv"
    src.write_text("a  b\n1  x;y\n", encoding="utf-8")
    assert main([str(src), "-d", ";", "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == 'a;b\n1;"x;y"\n'


def test_cli_errors(tmp_path, capsys, monkeypatch):
    code, _, err = run(capsys, ["-", "--names", "a,b"], "1  2  3\n", monkeypatch)
    assert code == 2 and "3 columns" in err
    code, _, err = run(capsys, [str(tmp_path / "missing.txt")])
    assert code == 1 and "no such file" in err
    code, _, err = run(capsys, ["-"], "\n  \n", monkeypatch)
    assert code == 1 and "no data lines" in err
    for bad in (["-w", "4,x"], ["-w", "4,0"], ["--gap", "0"]):
        monkeypatch.setattr("sys.stdin", io.StringIO("a\n"))
        with pytest.raises(SystemExit) as exc:
            main(["-", *bad])
        assert exc.value.code == 2
    code, _, err = run(capsys, ["-", "-w", "2,3"], "  ab\n1 2\n", monkeypatch)
    assert code == 2 and "blank header" in err

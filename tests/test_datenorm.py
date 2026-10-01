from datetime import date

import pytest

from minitools.datenorm import main, normalise_rows, parse_date


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026-09-28", date(2026, 9, 28)),
        ("2026/9/8", date(2026, 9, 8)),
        ("28-09-2026", date(2026, 9, 28)),
        ("28/09/2026", date(2026, 9, 28)),
        ("28.09.2026", date(2026, 9, 28)),
        ("03/04/2026", date(2026, 4, 3)),
        ("20260928", date(2026, 9, 28)),
        ("28 Sep 2026", date(2026, 9, 28)),
        ("28 September 2026", date(2026, 9, 28)),
        ("Sep 28, 2026", date(2026, 9, 28)),
        ("  28   Sep  2026 ", date(2026, 9, 28)),
    ],
)
def test_parse_date_formats(text, expected):
    assert parse_date(text) == expected


def test_monthfirst_swaps_numeric_order():
    assert parse_date("03/04/2026", monthfirst=True) == date(2026, 3, 4)
    assert parse_date("09/28/2026", monthfirst=True) == date(2026, 9, 28)


@pytest.mark.parametrize("text", ["", "   ", "n/a", "31/02/2026", "2026-13-01", "yesterday"])
def test_parse_date_rejects_invalid(text):
    assert parse_date(text) is None


def test_normalise_rows_reports_failures_and_keeps_them():
    rows = [{"d": "28/09/2026"}, {"d": "soon"}, {"d": ""}]
    assert normalise_rows(rows, "d") == [2]
    assert [r["d"] for r in rows] == ["2026-09-28", "soon", ""]


def test_cli_rewrites_column(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text('date,city\n28.09.2026,Breda\n"Sep 29, 2026",Tilburg\n', encoding="utf-8")
    assert main([str(src), str(dst), "-c", "date"]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == ["date,city", "2026-09-28,Breda", "2026-09-29,Tilburg"]


def test_cli_unknown_column(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("day\n2026-09-28\n", encoding="utf-8")
    assert main([str(src), str(tmp_path / "out.csv"), "-c", "date"]) == 1
    assert "not found" in capsys.readouterr().err


def test_cli_strict_fails_without_writing(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("date\nnot a date\n", encoding="utf-8")
    assert main([str(src), str(dst), "-c", "date", "--strict"]) == 1
    assert not dst.exists()


@pytest.mark.parametrize(
    "text",
    [
        "2026-09-28T14:30:00",
        "2026-09-28T14:30:00Z",
        "2026-09-28 14:30",
        "2026-09-28T23:59:59.123+02:00",
        "2026-09-28T00:15:00-0500",
    ],
)
def test_iso_timestamps_keep_their_date(text):
    assert parse_date(text) == date(2026, 9, 28)


@pytest.mark.parametrize("text", ["2026-09-28T25", "2026-09-28Tnoon", "2026-02-30T10:00", "2026-09-28 14:30 extra"])
def test_malformed_timestamps_are_rejected(text):
    assert parse_date(text) is None

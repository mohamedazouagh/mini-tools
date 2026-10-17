import random
from collections import Counter

import pytest

from minitools.csvsample import frac_sample, main, reservoir_sample

ROWS = [[str(i), f"name{i}"] for i in range(100)]


def test_reservoir_keeps_n_rows_in_file_order_and_is_seeded():
    a = reservoir_sample(iter(ROWS), 10, random.Random(1))
    b = reservoir_sample(iter(ROWS), 10, random.Random(1))
    assert a == b and len(a) == 10
    ids = [int(r[0]) for r in a]
    assert ids == sorted(ids) and len(set(ids)) == 10


def test_reservoir_returns_everything_when_n_is_large_or_zero_rows():
    assert reservoir_sample(iter(ROWS[:3]), 10, random.Random(0)) == ROWS[:3]
    assert reservoir_sample(iter(ROWS), 0, random.Random(0)) == []
    with pytest.raises(ValueError):
        reservoir_sample(iter(ROWS), -1, random.Random(0))


def test_reservoir_is_roughly_uniform():
    rng = random.Random(7)
    hits = Counter()
    for _ in range(4000):
        for r in reservoir_sample(iter(ROWS[:10]), 3, rng):
            hits[r[0]] += 1
    # each of 10 rows should be picked ~30% of 4000 = 1200 times
    assert all(1050 < hits[str(i)] < 1350 for i in range(10)), hits


def test_frac_sample_size_and_bounds():
    assert len(frac_sample(ROWS, 0.25, random.Random(0))) == 25
    assert frac_sample(ROWS, 0, random.Random(0)) == []
    assert frac_sample(ROWS, 1, random.Random(0)) == ROWS
    with pytest.raises(ValueError):
        frac_sample(ROWS, 1.5, random.Random(0))


def test_cli_header_semicolons_blank_lines_and_seed(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("﻿id;city\n1;Breda\n\n2;Tilburg\n3;Utrecht\n4;Delft\n", encoding="utf-8")
    assert main([str(src), "-n", "2", "--seed", "3", "-d", ";"]) == 0
    first = capsys.readouterr().out
    lines = first.splitlines()
    assert lines[0] == "id;city" and len(lines) == 3
    assert main([str(src), "-n", "2", "--seed", "3", "-d", ";"]) == 0
    assert capsys.readouterr().out == first


def test_cli_output_file_refuses_overwrite(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id\n1\n2\n3\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    assert main([str(src), "--frac", "1", "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "id\n1\n2\n3\n"
    assert main([str(src), "-n", "1", "-o", str(out)]) == 1
    assert "exists" in capsys.readouterr().err
    assert main([str(src), "-n", "1", "-o", str(out), "--force"]) == 0


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "missing.csv"), "-n", "1"]) == 1
    empty = tmp_path / "empty.csv"
    empty.write_text("\n\n", encoding="utf-8")
    assert main([str(empty), "-n", "1"]) == 1
    with pytest.raises(SystemExit):
        main([str(empty), "-n", "1", "--frac", "0.5"])
    with pytest.raises(SystemExit):
        main([str(empty), "--frac", "2"])

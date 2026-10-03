from minitools.renamer import find_conflicts, main, plan_renames


def _make(folder, *names):
    for n in names:
        (folder / n).write_text(n, encoding="utf-8")


def _names(folder):
    return sorted(p.name for p in folder.iterdir())


def test_plan_only_lists_changed_names_with_groups():
    names = ["IMG_002.jpg", "IMG_001.jpg", "notes.txt"]
    assert plan_renames(names, r"^IMG_(\d+)", r"trip_\1") == [
        ("IMG_001.jpg", "trip_001.jpg"),
        ("IMG_002.jpg", "trip_002.jpg"),
    ]


def test_plan_ignore_case():
    assert plan_renames(["Report.CSV"], r"\.csv$", ".csv", ignore_case=True) == [("Report.CSV", "Report.csv")]
    assert plan_renames(["Report.CSV"], r"\.csv$", ".csv") == []


def test_conflicts_duplicate_target_existing_file_and_bad_name():
    plan = [("a1.txt", "a.txt"), ("a2.txt", "a.txt")]
    assert any("would both become" in m for m in find_conflicts(plan, ["a1.txt", "a2.txt"]))
    assert any("already exists" in m for m in find_conflicts([("x.txt", "y.txt")], ["x.txt", "y.txt"]))
    assert any("not a valid" in m for m in find_conflicts([("x.txt", "")], ["x.txt"]))
    assert any("not a valid" in m for m in find_conflicts([("x.txt", "sub/x.txt")], ["x.txt"]))


def test_no_conflict_for_case_only_rename_or_chain():
    assert find_conflicts([("a.TXT", "a.txt")], ["a.TXT"]) == []
    assert find_conflicts([("a", "b"), ("b", "c")], ["a", "b"]) == []


def test_cli_dry_run_changes_nothing(tmp_path, capsys):
    _make(tmp_path, "IMG_1.jpg", "IMG_2.jpg")
    assert main([str(tmp_path), r"^IMG_", "pic_"]) == 0
    out = capsys.readouterr()
    assert "IMG_1.jpg -> pic_1.jpg" in out.out and "dry run: 2 file(s)" in out.err
    assert _names(tmp_path) == ["IMG_1.jpg", "IMG_2.jpg"]


def test_cli_apply_renames_and_keeps_content(tmp_path):
    _make(tmp_path, "IMG_1.jpg", "keep.txt")
    assert main([str(tmp_path), r"^IMG_", "pic_", "--apply", "--glob", "*.jpg"]) == 0
    assert _names(tmp_path) == ["keep.txt", "pic_1.jpg"]
    assert (tmp_path / "pic_1.jpg").read_text(encoding="utf-8") == "IMG_1.jpg"


def test_cli_apply_handles_chain_without_clobbering(tmp_path):
    # one plan where "f" -> "ff" while the existing "ff" -> "fff"
    _make(tmp_path, "f", "ff")
    assert main([str(tmp_path), r"^f", "ff", "--apply"]) == 0
    assert _names(tmp_path) == ["ff", "fff"]
    assert (tmp_path / "ff").read_text(encoding="utf-8") == "f"
    assert (tmp_path / "fff").read_text(encoding="utf-8") == "ff"


def test_cli_conflict_renames_nothing(tmp_path, capsys):
    _make(tmp_path, "a1.txt", "a2.txt")
    assert main([str(tmp_path), r"\d", "", "--apply"]) == 1
    assert "nothing renamed" in capsys.readouterr().err
    assert _names(tmp_path) == ["a1.txt", "a2.txt"]


def test_cli_bad_regex_and_missing_folder(tmp_path, capsys):
    assert main([str(tmp_path), "(", "x"]) == 1
    assert "bad pattern" in capsys.readouterr().err
    assert main([str(tmp_path / "nope"), "a", "b"]) == 1
    assert "no such folder" in capsys.readouterr().err

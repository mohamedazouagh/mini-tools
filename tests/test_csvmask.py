import hashlib
import hmac
import io

import pytest

from minitools.csvmask import ColumnError, email_token, hash_token, main, mask_rows, mask_value, parse_specs


def test_hash_token_is_stable_salted_and_trimmed():
    a = hash_token("ana@example.com", "s3cret")
    assert a == hmac.new(b"s3cret", b"ana@example.com", hashlib.sha256).hexdigest()[:12]
    assert hash_token("  ana@example.com ", "s3cret") == a
    assert hash_token("ana@example.com", "other") != a
    assert hash_token("Ana@Example.com", "s3cret") != a
    assert hash_token("Ana@Example.com", "s3cret", ignore_case=True) == a
    assert hash_token("   ", "s3cret") == ""


def test_mask_value_keeps_last_characters():
    assert mask_value("0612345678") == "******5678"
    assert mask_value(" 0612345678 ", keep=2) == "********78"
    assert mask_value("abc") == "***"
    assert mask_value("abcd") == "****"
    assert mask_value("secret", keep=0) == "******"
    assert mask_value("") == ""


def test_parse_specs_default_mode_and_errors():
    header = ["id", "email", "phone"]
    assert parse_specs(["email", "phone:mask", "id: blank"], header) == [(1, "hash"), (2, "mask"), (0, "blank")]
    with pytest.raises(ColumnError, match="unknown column\\(s\\): mail; available: id, email, phone"):
        parse_specs(["mail"], header)
    with pytest.raises(ColumnError, match="unknown mode 'scramble'"):
        parse_specs(["email:scramble"], header)
    with pytest.raises(ColumnError, match="more than once"):
        parse_specs(["email", "email:mask"], header)


def test_mask_rows_leaves_other_columns_and_short_rows_alone():
    rows = [["1", "ana@x.nl", "0611112222"], ["2"], ["3", "", "06"]]
    out = mask_rows(rows, [(1, "hash"), (2, "mask")], salt="k")
    assert out[0][0] == "1" and len(out[0][1]) == 12 and out[0][2] == "******2222"
    assert out[1] == ["2"]
    assert out[2] == ["3", "", "**"]
    assert rows[0][1] == "ana@x.nl"  # input not mutated


def test_cli_same_value_same_token_and_semicolons(tmp_path, capsys):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("﻿id;email;name\n1;ana@x.nl;Ana\n2;bas@x.nl;Bas\n3;ANA@x.nl;Ana B\n", encoding="utf-8")
    assert main([str(src), "-c", "email", "-c", "name:blank", "-i", "--salt", "k", "-d", ";", "-o", str(dst)]) == 0
    lines = dst.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "id;email;name"
    tokens = [line.split(";")[1] for line in lines[1:]]
    assert tokens[0] == tokens[2] != tokens[1]
    assert all(line.endswith(";") for line in lines[1:])
    assert "warning" not in capsys.readouterr().err


def test_cli_warns_without_salt_and_reads_env(monkeypatch, capsys):
    monkeypatch.delenv("CSVMASK_SALT", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO("email\na@b.c\n"))
    assert main(["-", "-c", "email"]) == 0
    assert "hashing without --salt" in capsys.readouterr().err
    monkeypatch.setenv("CSVMASK_SALT", "envsalt")
    monkeypatch.setattr("sys.stdin", io.StringIO("email\na@b.c\n"))
    assert main(["-", "-c", "email"]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"email\n{hash_token('a@b.c', 'envsalt')}\n"
    assert captured.err == ""


def test_cli_errors(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,phone\n1,0612\n", encoding="utf-8")
    assert main([str(src), "-c", "mobile"]) == 2
    assert "available: id, phone" in capsys.readouterr().err
    assert main([str(src), "-c", "phone:mask", "--keep", "-1"]) == 2
    assert main([str(tmp_path / "nope.csv"), "-c", "id"]) == 1


def test_email_token_keeps_domain_and_falls_back_to_hash():
    tok = email_token(" ana@Example.COM ", "k")
    assert tok == hash_token("ana", "k") + "@example.com"
    assert email_token("ana@example.com", "k") == tok
    assert email_token("Ana@example.com", "k") != tok
    assert email_token("Ana@example.com", "k", ignore_case=True) == tok
    for odd in ("no-at-sign", "@example.com", "ana@", "a@b@c"):
        assert email_token(odd, "k") == hash_token(odd, "k")
    assert email_token("  ", "k") == ""


def test_cli_email_mode_lets_you_count_per_domain(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,email\n1,ana@x.nl\n2,bas@y.com\n3,ana@x.nl\n4,\n", encoding="utf-8")
    assert main([str(src), "-c", "email:email"]) == 0
    out = capsys.readouterr()
    emails = [line.split(",")[1] for line in out.out.splitlines()[1:]]
    assert [e.split("@")[1] for e in emails[:3]] == ["x.nl", "y.com", "x.nl"]
    assert emails[0] == emails[2] and "ana" not in emails[0]
    assert emails[3] == ""
    assert "warning" in out.err  # no salt given

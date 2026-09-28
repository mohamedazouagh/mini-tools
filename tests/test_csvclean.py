from minitools.csvclean import clean_rows, main, snake


def test_snake():
    assert snake(" Order ID ") == "order_id"
    assert snake("unitPrice") == "unit_price"
    assert snake("Qty (pcs)") == "qty_pcs"


def test_clean_rows_trims_and_drops_empty():
    rows = [["Name", "City"], [" Mo ", "Breda "], ["", " "], ["Sara", "Tilburg"]]
    assert clean_rows(rows) == [["name", "city"], ["Mo", "Breda"], ["Sara", "Tilburg"]]


def test_dedupe_only_when_asked():
    rows = [["a"], ["x"], ["x "]]
    assert len(clean_rows(rows)) == 3
    assert clean_rows(rows, dedupe=True) == [["a"], ["x"]]


def test_cli_roundtrip(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.csv"
    src.write_text("Order ID,unitPrice\n 1 , 9.5\n,\n", encoding="utf-8")
    assert main([str(src), str(dst)]) == 0
    assert dst.read_text(encoding="utf-8").splitlines() == ["order_id,unit_price", "1,9.5"]

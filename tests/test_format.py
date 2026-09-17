from andopt.format import bar, human_bytes, table


def test_human_bytes_scales_units():
    assert human_bytes(512) == "512 B"
    assert human_bytes(2048) == "2.0 KB"
    assert human_bytes(5 * 1024**3) == "5.0 GB"


def test_bar_clamps_out_of_range_ratios():
    assert bar(1.5, width=4) == "[####]"
    assert bar(-0.2, width=4) == "[....]"
    assert bar(0.5, width=4) == "[##..]"


def test_table_aligns_columns():
    out = table([("a", "1"), ("bbb", "22")], ("name", "n"))
    lines = out.splitlines()
    assert lines[0].startswith("name")
    assert len(lines) == 4

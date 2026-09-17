from andopt import parse


DF_OUTPUT = """Filesystem     1K-blocks     Used Available Use% Mounted on
/dev/block/dm-4  113246208 89104384  24141824  79% /data
tmpfs              3907584      876   3906708   1% /dev
/dev/block/sda12   3002368  2957312     45056  99% /system
"""


def test_parse_df_extracts_filesystems():
    filesystems = parse.parse_df(DF_OUTPUT)
    mounts = [fs.mount for fs in filesystems]
    assert mounts == ["/data", "/dev", "/system"]

    data = filesystems[0]
    assert data.size_bytes == 113246208 * 1024
    assert data.used_bytes == 89104384 * 1024
    assert 0.78 < data.used_ratio < 0.80


def test_parse_df_ignores_header_and_garbage():
    assert parse.parse_df("Filesystem 1K-blocks\nnonsense line\n") == []


def test_parse_df_used_ratio_is_zero_for_empty_filesystem():
    fs = parse.parse_df("none 0 0 0 0% /empty")[0]
    assert fs.used_ratio == 0.0


def test_parse_packages_dedupes_and_sorts():
    output = "package:com.b\npackage:com.a\npackage:com.a\n\ngarbage\n"
    assert parse.parse_packages(output) == ["com.a", "com.b"]


def test_parse_packages_handles_path_prefixed_form():
    output = "package:/data/app/Foo/base.apk=com.example.foo\n"
    assert parse.parse_packages(output) == ["com.example.foo"]


def test_parse_battery_reads_key_values():
    output = """Current Battery Service state:
  AC powered: false
  status: 3
  health: 2
  level: 64
  temperature: 312
"""
    values = parse.parse_battery(output)
    assert values["level"] == "64"
    assert values["temperature"] == "312"
    assert values["health"] == "2"
    assert "AC powered" not in values


def test_parse_meminfo_converts_to_bytes():
    output = "MemTotal:        7845112 kB\nMemFree:  204800 kB\nMemAvailable:  3145728 kB\nBuffers: 1 kB\n"
    mem = parse.parse_meminfo(output)
    assert mem["MemTotal"] == 7845112 * 1024
    assert mem["MemAvailable"] == 3145728 * 1024
    assert "Buffers" not in mem

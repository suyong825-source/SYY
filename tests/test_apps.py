from andopt import adb
from andopt.commands import apps


def test_find_bloat_skips_already_disabled(monkeypatch):
    bloat_pkg = "com.facebook.appmanager"
    other_pkg = "com.android.bips"

    def fake_shell(command, serial=None, timeout=60):
        if command == "pm list packages":
            return f"package:{bloat_pkg}\npackage:{other_pkg}\npackage:com.example.app\n"
        if command == "pm list packages -d":
            return f"package:{other_pkg}\n"
        raise AssertionError(command)

    monkeypatch.setattr(adb, "shell", fake_shell)
    found = apps.find_bloat("X")
    assert [pkg for pkg, _ in found] == [bloat_pkg]


def test_clear_cache_all_uses_trim_caches(monkeypatch):
    calls = []
    monkeypatch.setattr(
        adb, "shell", lambda cmd, serial=None, timeout=60: calls.append(cmd) or ""
    )
    apps.clear_cache("X")
    assert calls == ["pm trim-caches 999G"]


def test_clear_cache_per_package_is_cache_only(monkeypatch):
    calls = []
    monkeypatch.setattr(
        adb, "shell", lambda cmd, serial=None, timeout=60: calls.append(cmd) or ""
    )
    apps.clear_cache("X", ["com.example.a"])
    assert calls == ["pm clear --cache-only com.example.a"]


def test_disable_uses_reversible_disable_user(monkeypatch):
    calls = []
    monkeypatch.setattr(
        adb, "shell", lambda cmd, serial=None, timeout=60: calls.append(cmd) or ""
    )
    apps.disable_packages("X", ["com.example.a"])
    assert calls == ["pm disable-user --user 0 com.example.a"]


def test_disable_reports_per_package_failure(monkeypatch):
    def fake_shell(cmd, serial=None, timeout=60):
        raise adb.AdbError("권한 없음")

    monkeypatch.setattr(adb, "shell", fake_shell)
    out = apps.disable_packages("X", ["com.example.a"])
    assert "✗ com.example.a" in out

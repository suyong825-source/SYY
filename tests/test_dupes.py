"""중복 파일 탐지 로직 테스트 — 실제 기기 불필요."""

from andopt.commands.dupes import DupeGroup, delete_dupes, find_dupes, show_dupes
from andopt import adb


# ── _scan_sizes 파싱 ─────────────────────────────────────────

def _make_stat_output(*entries):
    """(size, path) 목록을 stat -c '%s %n' 출력 형식으로 변환."""
    return "\n".join(f"{size} {path}" for size, path in entries)


def test_find_dupes_groups_same_hash(monkeypatch):
    stat_out = _make_stat_output(
        (1024, "/storage/emulated/0/Download/a.jpg"),
        (1024, "/storage/emulated/0/Download/a_copy.jpg"),
        (2048, "/storage/emulated/0/Download/b.mp4"),
    )
    hash_out = (
        "d41d8cd98f00b204e9800998ecf8427e  /storage/emulated/0/Download/a.jpg\n"
        "d41d8cd98f00b204e9800998ecf8427e  /storage/emulated/0/Download/a_copy.jpg\n"
    )

    calls = []

    def fake_shell(cmd, serial=None, timeout=60):
        calls.append(cmd)
        if "stat" in cmd:
            return stat_out
        if "md5sum" in cmd:
            return hash_out
        return ""

    monkeypatch.setattr(adb, "shell", fake_shell)
    groups = find_dupes("X", root="/storage/emulated/0/Download")
    assert len(groups) == 1
    g = groups[0]
    assert g.size_bytes == 1024
    assert len(g.paths) == 2


def test_find_dupes_no_duplicates(monkeypatch):
    stat_out = _make_stat_output(
        (1024, "/sdcard/a.jpg"),
        (2048, "/sdcard/b.jpg"),
    )
    monkeypatch.setattr(adb, "shell", lambda cmd, serial=None, timeout=60: stat_out if "stat" in cmd else "")
    groups = find_dupes("X")
    assert groups == []


def test_zero_size_files_ignored(monkeypatch):
    stat_out = _make_stat_output(
        (0, "/sdcard/.nomedia"),
        (0, "/sdcard/empty2"),
    )
    monkeypatch.setattr(adb, "shell", lambda cmd, serial=None, timeout=60: stat_out if "stat" in cmd else "")
    groups = find_dupes("X")
    assert groups == []


# ── DupeGroup ────────────────────────────────────────────────

def test_keeper_prefers_shorter_path():
    g = DupeGroup(
        size_bytes=1024,
        file_hash="abc",
        paths=[
            "/storage/emulated/0/Download/copy/photo.jpg",
            "/storage/emulated/0/DCIM/photo.jpg",
        ],
    )
    assert g.keeper() == "/storage/emulated/0/DCIM/photo.jpg"


def test_duplicates_excludes_keeper():
    g = DupeGroup(
        size_bytes=1024,
        file_hash="abc",
        paths=["/a/original.jpg", "/b/copy.jpg", "/c/copy2.jpg"],
    )
    keeper = g.keeper()
    assert keeper not in g.duplicates()
    assert len(g.duplicates()) == 2


def test_waste_bytes():
    g = DupeGroup(size_bytes=1000, file_hash="x", paths=["a", "b", "c"])
    assert g.waste_bytes == 2000


# ── show_dupes ───────────────────────────────────────────────

def test_show_dupes_empty():
    assert show_dupes([]) == "중복 파일이 없습니다."


def test_show_dupes_contains_summary():
    g = DupeGroup(size_bytes=500, file_hash="h", paths=["/a/f.jpg", "/b/f.jpg"])
    out = show_dupes([g])
    assert "중복 그룹 1개" in out
    assert "삭제 대상" in out


# ── delete_dupes ─────────────────────────────────────────────

def test_delete_dupes_removes_non_keeper(monkeypatch):
    deleted = []
    monkeypatch.setattr(adb, "shell", lambda cmd, serial=None, timeout=60: deleted.append(cmd) or "")

    # keeper는 경로가 짧은 쪽: /b/f.jpg(8) < /a/original.jpg(15)
    g = DupeGroup(
        size_bytes=100,
        file_hash="h",
        paths=["/a/original.jpg", "/b/f.jpg"],
    )
    result = delete_dupes("X", [g])
    assert "1개 삭제" in result
    assert any("/a/original.jpg" in c for c in deleted)
    assert not any("/b/f.jpg" in c for c in deleted)


def test_delete_dupes_reports_errors(monkeypatch):
    def fail(cmd, serial=None, timeout=60):
        raise adb.AdbError("권한 없음")

    monkeypatch.setattr(adb, "shell", fail)
    g = DupeGroup(size_bytes=100, file_hash="h", paths=["/a/f.jpg", "/b/f.jpg"])
    result = delete_dupes("X", [g])
    assert "✗" in result

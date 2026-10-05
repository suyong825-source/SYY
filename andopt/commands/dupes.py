"""중복 파일 탐지 및 삭제."""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import adb
from ..format import human_bytes, table

_DEFAULT_ROOT = "/storage/emulated/0"
_STAT_CMD = "find {root} -type f -exec stat -c '%s %n' {{}} + 2>/dev/null"
_HASH_BATCH = 40  # 한 번에 md5sum에 넘기는 파일 수


@dataclass
class DupeGroup:
    size_bytes: int
    file_hash: str
    paths: list[str] = field(default_factory=list)

    @property
    def waste_bytes(self) -> int:
        return self.size_bytes * (len(self.paths) - 1)

    def keeper(self) -> str:
        # 경로가 짧을수록(상위 폴더) 원본일 가능성이 높다
        return min(self.paths, key=lambda p: (len(p), p))

    def duplicates(self) -> list[str]:
        k = self.keeper()
        return [p for p in self.paths if p != k]


def _scan_sizes(serial: str, root: str) -> dict[int, list[str]]:
    """기기에서 파일 크기 목록을 가져와 크기별로 묶는다."""
    output = adb.shell(_STAT_CMD.format(root=root), serial=serial, timeout=300)
    by_size: dict[int, list[str]] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        path = parts[1].strip()
        if size == 0 or not path:
            continue
        by_size.setdefault(size, []).append(path)
    # 같은 크기인 파일이 2개 이상인 그룹만
    return {s: p for s, p in by_size.items() if len(p) > 1}


def _hash_group(serial: str, paths: list[str]) -> dict[str, list[str]]:
    """파일들의 md5 해시를 구해 해시별로 묶는다."""
    by_hash: dict[str, list[str]] = {}
    for i in range(0, len(paths), _HASH_BATCH):
        batch = paths[i : i + _HASH_BATCH]
        quoted = " ".join(f'"{p}"' for p in batch)
        try:
            output = adb.shell(f"md5sum {quoted} 2>/dev/null", serial=serial, timeout=120)
        except adb.AdbError:
            continue
        for line in output.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and len(parts[0]) == 32:
                h, path = parts
                by_hash.setdefault(h, []).append(path.strip())
    return {h: p for h, p in by_hash.items() if len(p) > 1}


def find_dupes(serial: str, root: str = _DEFAULT_ROOT) -> list[DupeGroup]:
    """중복 파일 그룹 목록을 반환한다. 낭비 용량 내림차순."""
    print("파일 목록 스캔 중… (수십 초 소요될 수 있음)", flush=True)
    size_map = _scan_sizes(serial, root)
    if not size_map:
        return []

    total_candidates = sum(len(p) for p in size_map.values())
    print(f"크기 중복 후보 {total_candidates}개, 해시 계산 중…", flush=True)

    groups: list[DupeGroup] = []
    for size, paths in size_map.items():
        for h, dupe_paths in _hash_group(serial, paths).items():
            groups.append(DupeGroup(size_bytes=size, file_hash=h, paths=sorted(dupe_paths)))

    return sorted(groups, key=lambda g: g.waste_bytes, reverse=True)


def show_dupes(groups: list[DupeGroup], limit: int = 20) -> str:
    if not groups:
        return "중복 파일이 없습니다."

    total_waste = sum(g.waste_bytes for g in groups)
    total_files = sum(len(g.duplicates()) for g in groups)
    lines = [
        f"중복 그룹 {len(groups)}개  /  삭제 후보 {total_files}개  /  절약 가능 {human_bytes(total_waste)}\n"
    ]

    shown = groups[:limit]
    rows = []
    for g in shown:
        rows.append((human_bytes(g.size_bytes), str(len(g.paths)), human_bytes(g.waste_bytes), g.keeper()))
        for dup in g.duplicates():
            rows.append(("", "", "", f"  └ 삭제 대상: {dup}"))

    lines.append(table(rows, ("크기", "개수", "낭비", "경로")))
    if len(groups) > limit:
        lines.append(f"\n… 외 {len(groups) - limit}개 그룹 생략")
    return "\n".join(lines)


def delete_dupes(serial: str, groups: list[DupeGroup]) -> str:
    """각 그룹에서 원본 1개를 남기고 나머지를 삭제한다."""
    deleted = freed = 0
    errors: list[str] = []
    for g in groups:
        for path in g.duplicates():
            try:
                adb.shell(f'rm "{path}"', serial=serial)
                deleted += 1
                freed += g.size_bytes
            except adb.AdbError as exc:
                errors.append(f"  ✗ {path}: {exc}")
    result = f"파일 {deleted}개 삭제, {human_bytes(freed)} 확보"
    if errors:
        result += "\n\n오류:\n" + "\n".join(errors)
    return result

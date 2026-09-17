"""기기 출력 파서. 순수 함수만 두어 기기 없이도 테스트 가능하게 한다."""

from __future__ import annotations

import re
from dataclasses import dataclass

_DF_LINE = re.compile(
    r"^\S+\s+(?P<size>\d+)\s+(?P<used>\d+)\s+(?P<avail>\d+)\s+(?P<pct>\d+)%\s+(?P<mount>\S+)$"
)


@dataclass(frozen=True)
class Filesystem:
    mount: str
    size_bytes: int
    used_bytes: int
    avail_bytes: int

    @property
    def used_ratio(self) -> float:
        return self.used_bytes / self.size_bytes if self.size_bytes else 0.0


def parse_df(output: str) -> list[Filesystem]:
    """`df -k` 출력을 파싱한다 (1K 블록 단위)."""
    results = []
    for line in output.splitlines():
        match = _DF_LINE.match(line.strip())
        if not match:
            continue
        results.append(
            Filesystem(
                mount=match.group("mount"),
                size_bytes=int(match.group("size")) * 1024,
                used_bytes=int(match.group("used")) * 1024,
                avail_bytes=int(match.group("avail")) * 1024,
            )
        )
    return results


def parse_packages(output: str) -> list[str]:
    """`pm list packages` 출력에서 패키지명을 뽑는다."""
    packages = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            name = line[len("package:") :].split("=")[-1].strip()
            if name:
                packages.append(name)
    return sorted(set(packages))


def parse_battery(output: str) -> dict[str, str]:
    """`dumpsys battery` 출력을 key/value로 파싱한다."""
    values: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key and value and " " not in key:
            values[key] = value
    return values


_MEM_LINE = re.compile(r"^(?P<key>MemTotal|MemFree|MemAvailable):\s+(?P<kb>\d+)\s*kB$")


def parse_meminfo(output: str) -> dict[str, int]:
    """`cat /proc/meminfo` 에서 총/가용 메모리를 바이트로 뽑는다."""
    values: dict[str, int] = {}
    for line in output.splitlines():
        match = _MEM_LINE.match(line.strip())
        if match:
            values[match.group("key")] = int(match.group("kb")) * 1024
    return values

"""ADB 래퍼: 기기 탐색과 셸 명령 실행."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


class AdbError(RuntimeError):
    """adb 실행 실패."""


@dataclass(frozen=True)
class Device:
    serial: str
    state: str

    @property
    def usable(self) -> bool:
        return self.state == "device"


def adb_path() -> str:
    path = shutil.which("adb")
    if path is None:
        raise AdbError(
            "adb를 찾을 수 없습니다. Android Platform Tools를 설치하고 PATH에 추가하세요."
        )
    return path


def run(args: list[str], serial: str | None = None, timeout: int = 60) -> str:
    cmd = [adb_path()]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbError(f"명령 시간 초과: {' '.join(args)}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise AdbError(f"adb 실패 ({' '.join(args)}): {detail}")
    return proc.stdout


def shell(command: str, serial: str | None = None, timeout: int = 60) -> str:
    return run(["shell", command], serial=serial, timeout=timeout)


def list_devices() -> list[Device]:
    out = run(["devices"])
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append(Device(serial=parts[0], state=parts[1]))
    return devices


def resolve_device(serial: str | None = None) -> Device:
    devices = list_devices()
    usable = [d for d in devices if d.usable]
    if serial:
        for d in devices:
            if d.serial == serial:
                if not d.usable:
                    raise AdbError(f"기기 {serial} 상태가 '{d.state}'입니다.")
                return d
        raise AdbError(f"기기 {serial}를 찾을 수 없습니다.")
    if not usable:
        if devices:
            states = ", ".join(f"{d.serial}={d.state}" for d in devices)
            raise AdbError(f"사용 가능한 기기가 없습니다 ({states}). USB 디버깅 승인을 확인하세요.")
        raise AdbError("연결된 기기가 없습니다. USB 디버깅을 켜고 케이블을 연결하세요.")
    if len(usable) > 1:
        serials = ", ".join(d.serial for d in usable)
        raise AdbError(f"기기가 여러 대입니다. --serial로 지정하세요: {serials}")
    return usable[0]

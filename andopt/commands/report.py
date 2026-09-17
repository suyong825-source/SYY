"""진단 리포트: 기기 정보, 저장공간, 메모리, 배터리."""

from __future__ import annotations

from .. import adb, parse
from ..format import bar, human_bytes, table

_PROPS = {
    "제조사": "ro.product.manufacturer",
    "모델": "ro.product.model",
    "안드로이드": "ro.build.version.release",
    "SDK": "ro.build.version.sdk",
    "빌드": "ro.build.display.id",
}

_INTERESTING_MOUNTS = ("/data", "/storage/emulated", "/system", "/cache")


def device_info(serial: str) -> str:
    lines = []
    for label, prop in _PROPS.items():
        value = adb.shell(f"getprop {prop}", serial=serial).strip() or "-"
        lines.append(f"{label}: {value}")
    lines.append(f"시리얼: {serial}")
    return "\n".join(lines)


def storage(serial: str) -> str:
    filesystems = parse.parse_df(adb.shell("df -k", serial=serial))
    rows = []
    for fs in filesystems:
        if not fs.mount.startswith(_INTERESTING_MOUNTS):
            continue
        rows.append(
            (
                fs.mount,
                human_bytes(fs.size_bytes),
                human_bytes(fs.used_bytes),
                human_bytes(fs.avail_bytes),
                f"{bar(fs.used_ratio)} {fs.used_ratio * 100:.0f}%",
            )
        )
    if not rows:
        return "저장공간 정보를 읽지 못했습니다."
    return table(rows, ("마운트", "전체", "사용", "여유", "사용률"))


def memory(serial: str) -> str:
    mem = parse.parse_meminfo(adb.shell("cat /proc/meminfo", serial=serial))
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", mem.get("MemFree", 0))
    if not total:
        return "메모리 정보를 읽지 못했습니다."
    used_ratio = (total - available) / total
    return (
        f"전체 {human_bytes(total)} / 가용 {human_bytes(available)}\n"
        f"{bar(used_ratio)} 사용률 {used_ratio * 100:.0f}%"
    )


def battery(serial: str) -> str:
    values = parse.parse_battery(adb.shell("dumpsys battery", serial=serial))
    if not values:
        return "배터리 정보를 읽지 못했습니다."
    level = values.get("level", "?")
    health_map = {"2": "양호", "3": "과열", "4": "수명 종료", "5": "과전압", "7": "저온"}
    health = health_map.get(values.get("health", ""), values.get("health", "?"))
    temp_raw = values.get("temperature")
    temperature = f"{int(temp_raw) / 10:.1f}°C" if temp_raw and temp_raw.isdigit() else "?"
    charging = "충전 중" if values.get("status") == "2" else "미충전"
    lines = [
        f"잔량: {level}%  {bar(int(level) / 100) if level.isdigit() else ''}",
        f"상태: {charging}   건강도: {health}   온도: {temperature}",
    ]
    if temp_raw and temp_raw.isdigit() and int(temp_raw) / 10 >= 40:
        lines.append("⚠ 온도가 높습니다. 충전 중이라면 케이스를 벗기고 잠시 식히세요.")
    return "\n".join(lines)


def full_report(serial: str) -> str:
    sections = [
        ("기기 정보", device_info(serial)),
        ("저장공간", storage(serial)),
        ("메모리", memory(serial)),
        ("배터리", battery(serial)),
    ]
    out = []
    for title, body in sections:
        out.append(f"\n── {title} " + "─" * max(0, 40 - len(title)))
        out.append(body)
    return "\n".join(out).strip()

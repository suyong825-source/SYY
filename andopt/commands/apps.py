"""앱 목록/캐시 정리/블로트웨어 비활성화."""

from __future__ import annotations

from .. import adb, parse
from ..format import table

# 비활성화해도 시스템이 정상 동작하는 것으로 널리 알려진 선탑재 앱들.
# 보수적으로 유지한다 — 통신/카메라/설정 등 핵심 구성요소는 절대 넣지 않는다.
KNOWN_BLOAT = {
    "com.facebook.appmanager": "Facebook 설치 관리자",
    "com.facebook.services": "Facebook 백그라운드 서비스",
    "com.facebook.system": "Facebook 시스템 스텁",
    "com.android.bips": "기본 인쇄 서비스",
    "com.android.printspooler": "인쇄 스풀러",
    "com.google.android.apps.tachyon": "Google Meet(구 Duo)",
    "com.google.android.videos": "Google TV",
    "com.google.android.apps.books": "Play 북스",
    "com.google.android.feedback": "Google 피드백",
    "com.samsung.android.game.gamehome": "삼성 게임 런처",
    "com.samsung.android.bixby.agent": "Bixby 음성",
    "com.samsung.android.app.spage": "삼성 프리",
}


def list_third_party(serial: str) -> list[str]:
    return parse.parse_packages(adb.shell("pm list packages -3", serial=serial))


def list_disabled(serial: str) -> list[str]:
    return parse.parse_packages(adb.shell("pm list packages -d", serial=serial))


def show_apps(serial: str) -> str:
    third_party = list_third_party(serial)
    disabled = set(list_disabled(serial))
    rows = [(pkg, "비활성" if pkg in disabled else "활성") for pkg in third_party]
    if not rows:
        return "설치된 사용자 앱이 없습니다."
    return f"사용자 앱 {len(rows)}개\n\n" + table(rows, ("패키지", "상태"))


def clear_cache(serial: str, packages: list[str] | None = None) -> str:
    """앱 캐시를 비운다. 사용자 데이터는 건드리지 않는다 (`pm trim-caches` 사용)."""
    if packages:
        results = []
        for pkg in packages:
            try:
                adb.shell(f"pm clear --cache-only {pkg}", serial=serial)
                results.append(f"  ✓ {pkg}")
            except adb.AdbError as exc:
                results.append(f"  ✗ {pkg}: {exc}")
        return "앱별 캐시 정리:\n" + "\n".join(results)
    # 999GB를 목표 여유공간으로 지정 = 정리 가능한 캐시를 전부 비움.
    adb.shell("pm trim-caches 999G", serial=serial)
    return "전체 앱 캐시를 정리했습니다."


def find_bloat(serial: str) -> list[tuple[str, str]]:
    installed = set(parse.parse_packages(adb.shell("pm list packages", serial=serial)))
    disabled = set(list_disabled(serial))
    return [
        (pkg, label)
        for pkg, label in sorted(KNOWN_BLOAT.items())
        if pkg in installed and pkg not in disabled
    ]


def show_bloat(serial: str) -> str:
    found = find_bloat(serial)
    if not found:
        return "알려진 선탑재 앱 중 비활성화할 대상이 없습니다."
    body = table([(pkg, label) for pkg, label in found], ("패키지", "설명"))
    return (
        f"비활성화 후보 {len(found)}개\n\n{body}\n\n"
        "비활성화하려면: andopt bloat --disable\n"
        "되돌리려면:   andopt enable <패키지명>"
    )


def disable_packages(serial: str, packages: list[str]) -> str:
    """현재 사용자에 대해서만 비활성화한다 — 언제든 enable로 되돌릴 수 있다."""
    results = []
    for pkg in packages:
        try:
            adb.shell(f"pm disable-user --user 0 {pkg}", serial=serial)
            results.append(f"  ✓ {pkg} 비활성화")
        except adb.AdbError as exc:
            results.append(f"  ✗ {pkg}: {exc}")
    return "\n".join(results)


def enable_packages(serial: str, packages: list[str]) -> str:
    results = []
    for pkg in packages:
        try:
            adb.shell(f"pm enable --user 0 {pkg}", serial=serial)
            results.append(f"  ✓ {pkg} 활성화")
        except adb.AdbError as exc:
            results.append(f"  ✗ {pkg}: {exc}")
    return "\n".join(results)

"""andopt 커맨드라인 인터페이스."""

from __future__ import annotations

import argparse
import sys

from . import __version__, adb
from .commands import apps, report


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="andopt",
        description="ADB로 안드로이드 기기를 진단하고 최적화합니다.",
    )
    parser.add_argument("--version", action="version", version=f"andopt {__version__}")
    parser.add_argument("--serial", help="대상 기기 시리얼 (여러 대 연결 시 필수)")
    parser.add_argument("-y", "--yes", action="store_true", help="확인 없이 실행")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="연결된 기기 목록")
    sub.add_parser("report", help="기기/저장공간/메모리/배터리 종합 진단")
    sub.add_parser("storage", help="저장공간 사용량")
    sub.add_parser("battery", help="배터리 상태")
    sub.add_parser("memory", help="메모리 사용량")
    sub.add_parser("apps", help="설치된 사용자 앱 목록")

    clean = sub.add_parser("clean", help="앱 캐시 정리 (사용자 데이터는 보존)")
    clean.add_argument("packages", nargs="*", help="대상 패키지 (생략 시 전체)")

    bloat = sub.add_parser("bloat", help="알려진 선탑재 앱 확인/비활성화")
    bloat.add_argument("--disable", action="store_true", help="후보를 실제로 비활성화")

    disable = sub.add_parser("disable", help="지정한 패키지를 비활성화")
    disable.add_argument("packages", nargs="+")

    enable = sub.add_parser("enable", help="비활성화한 패키지를 되돌림")
    enable.add_argument("packages", nargs="+")

    return parser


def _dispatch(args: argparse.Namespace) -> str:
    if args.command == "devices":
        devices = adb.list_devices()
        if not devices:
            return "연결된 기기가 없습니다."
        return "\n".join(f"{d.serial}\t{d.state}" for d in devices)

    serial = adb.resolve_device(args.serial).serial

    if args.command == "report":
        return report.full_report(serial)
    if args.command == "storage":
        return report.storage(serial)
    if args.command == "battery":
        return report.battery(serial)
    if args.command == "memory":
        return report.memory(serial)
    if args.command == "apps":
        return apps.show_apps(serial)
    if args.command == "clean":
        target = ", ".join(args.packages) if args.packages else "모든 앱"
        if not _confirm(f"{target}의 캐시를 정리할까요?", args.yes):
            return "취소했습니다."
        return apps.clear_cache(serial, args.packages or None)
    if args.command == "bloat":
        if not args.disable:
            return apps.show_bloat(serial)
        found = apps.find_bloat(serial)
        if not found:
            return "비활성화할 대상이 없습니다."
        packages = [pkg for pkg, _ in found]
        print(apps.show_bloat(serial))
        if not _confirm(f"위 {len(packages)}개를 비활성화할까요?", args.yes):
            return "취소했습니다."
        return apps.disable_packages(serial, packages)
    if args.command == "disable":
        if not _confirm(f"{len(args.packages)}개 패키지를 비활성화할까요?", args.yes):
            return "취소했습니다."
        return apps.disable_packages(serial, args.packages)
    if args.command == "enable":
        return apps.enable_packages(serial, args.packages)

    raise AssertionError(f"처리되지 않은 명령: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        print(_dispatch(args))
    except adb.AdbError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n중단했습니다.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

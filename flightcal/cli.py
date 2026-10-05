"""flightcal 커맨드라인 인터페이스."""

from __future__ import annotations

import argparse
import sys

from . import airports


def _cmd_auth(_args: argparse.Namespace) -> int:
    from .auth import get_credentials, TOKEN_PATH
    try:
        get_credentials()
        print(f"인증 완료. 토큰 저장됨: {TOKEN_PATH}")
        return 0
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1


def _cmd_sync(args: argparse.Namespace) -> int:
    from .gmail import fetch_flight_emails
    from .parse import parse_email
    from .calendar import sync_legs

    print(f"Gmail에서 최근 {args.since}일 항공권 이메일 검색 중...")
    try:
        emails = fetch_flight_emails(since_days=args.since)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    if not emails:
        print("항공권 이메일을 찾지 못했습니다.")
        return 0

    all_legs = []
    for email in emails:
        legs = parse_email(email.subject, email.body)
        all_legs.extend(legs)

    if not all_legs:
        print(f"이메일 {len(emails)}개를 읽었지만 항공편 정보를 파싱하지 못했습니다.")
        return 0

    print(f"항공편 {len(all_legs)}개 발견. 캘린더에 등록 중...")
    results = sync_legs(all_legs)

    for r in results:
        leg = r.leg
        try:
            origin_tz = airports.timezone(leg.origin)
            dest_tz = airports.timezone(leg.dest)
        except KeyError:
            origin_tz = dest_tz = "?"
        status = "이미 존재" if r.skipped else "등록 완료"
        print(
            f"  [{status}] {leg.flight_no or '-':>6}  "
            f"{leg.origin}({origin_tz}) {leg.depart.strftime('%m/%d %H:%M')} → "
            f"{leg.dest}({dest_tz}) {leg.arrive.strftime('%m/%d %H:%M')}"
        )
        if not r.skipped:
            print(f"           {r.html_link}")

    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    """이메일을 실제로 가져오지 않고 파싱만 테스트한다."""
    from .parse import parse_email
    text = sys.stdin.read()
    legs = parse_email("", text)
    if not legs:
        print("항공편 정보를 찾지 못했습니다.")
        return 1
    for leg in legs:
        try:
            origin_tz = airports.timezone(leg.origin)
            dest_tz = airports.timezone(leg.dest)
        except KeyError as e:
            print(f"알 수 없는 공항 코드: {e}")
            continue
        print(
            f"{leg.flight_no or '(편명 없음)':>7}  "
            f"{leg.origin} {leg.depart.strftime('%Y-%m-%d %H:%M')} [{origin_tz}]"
            f"  →  {leg.dest} {leg.arrive.strftime('%Y-%m-%d %H:%M')} [{dest_tz}]"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flightcal",
        description="Gmail 항공권 이메일 → Google 캘린더 현지 시각 등록",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="Google 계정 인증 (최초 1회)")

    sync = sub.add_parser("sync", help="Gmail 검색 후 캘린더에 등록")
    sync.add_argument(
        "--since", type=int, default=60, metavar="일수",
        help="최근 며칠치 이메일을 볼지 (기본: 60)",
    )

    sub.add_parser(
        "check",
        help="stdin으로 받은 텍스트를 파싱만 해서 결과 출력 (API 불필요)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {"auth": _cmd_auth, "sync": _cmd_sync, "check": _cmd_check}
    try:
        return dispatch[args.command](args)
    except KeyboardInterrupt:
        print("\n중단했습니다.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

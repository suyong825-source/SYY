"""courtfinder 커맨드라인."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

from . import __version__
from . import history, predict
from .fetch import FetchError, fetch_all, fetch_detail
from .parser import Service, parse_detail
from .render import render, summarize


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(services: list[dict], path: Path) -> None:
    path.write_text(
        json.dumps(services, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="courtfinder",
        description="서울시 공공예약 테니스장을 날짜별로 볼 수 있는 HTML을 만듭니다.",
    )
    parser.add_argument("--version", action="version", version=f"courtfinder {__version__}")
    parser.add_argument("-o", "--out", default="tennis.html", help="생성할 HTML 경로")
    parser.add_argument("--json", default="courts.json", help="수집 결과 JSON 경로")
    parser.add_argument("--delay", type=float, default=1.0, help="요청 간격(초)")
    parser.add_argument("--max-pages", type=int, help="가져올 최대 페이지 수 (시험용)")
    parser.add_argument(
        "--offline", action="store_true", help="수집을 건너뛰고 기존 JSON으로 HTML만 생성"
    )
    parser.add_argument(
        "--details", action="store_true",
        help="각 건의 상세 페이지도 읽어 접수 '시각'까지 확보 (요청이 크게 늘어납니다)",
    )
    parser.add_argument("--history", default="history.jsonl", help="관찰 기록 파일")
    parser.add_argument(
        "--upcoming", action="store_true",
        help="HTML을 만들지 않고, 코트별 다음 접수 개방 시각과 알람 시각만 출력",
    )
    parser.add_argument(
        "--minutes", type=int, default=10, help="알람을 개방 몇 분 전에 둘지"
    )
    return parser


def _enrich_with_times(services: list[dict], delay: float,
                       known: dict[str, dict] | None = None) -> int:
    """접수 '시각'은 상세 페이지에만 있다.

    이미 관찰 기록에 시각이 있는 건은 그 값을 그대로 쓰고, 처음 보는 건만
    상세 페이지를 읽는다. 매일 돌려도 요청이 몇 건 수준에 머물게 하기 위함이다.
    """
    known = known or {}
    filled = 0

    for service in services:
        seen = known.get(service.get("svc_id", ""))
        if seen and seen.get("rcpt_open_at"):
            service.setdefault("rcpt_open_at", "")
            service["rcpt_open_at"] = seen["rcpt_open_at"]
            service["rcpt_close_at"] = seen.get("rcpt_close_at", "")

    todo = [s for s in services if not s.get("rcpt_open_at")]
    if todo:
        print(f"  처음 보는 {len(todo)}건만 상세를 읽습니다")
    for i, service in enumerate(todo, 1):
        try:
            service.update(parse_detail(fetch_detail(service["svc_id"])))
        except FetchError as exc:
            print(f"  ! {exc}")
            continue
        if service.get("rcpt_open_at"):
            filled += 1
        if i % 50 == 0:
            print(f"  상세 {i}/{len(todo)}", flush=True)
        time.sleep(delay)
    return filled


def _print_upcoming(records: list[dict], minutes: int) -> None:
    rows = predict.upcoming(records)
    if not rows:
        print("앞으로 45일 안에 예상되는 접수 개방이 없습니다.")
        print("관찰 기록이 더 쌓이면(회차 2번 이상) 예측이 시작됩니다.")
        return

    print(f"\n다음 접수 개방 — {len(rows)}곳  (KST)\n")
    print(f"{'개방 시각':17s} {'알람':17s} {'근거':7s} {'회차':4s} 코트")
    print("-" * 86)
    for row in rows:
        alarm = predict.alarm_time(row["opens_at"], minutes)
        kind = "확정" if row["kind"] == "confirmed" else "추정"
        print(
            f"{row['opens_at'].replace('T', ' '):17s} "
            f"{alarm.strftime('%Y-%m-%d %H:%M'):17s} "
            f"{kind:7s} {row['rounds_seen']:<4d} "
            f"{row['place']}({row['area']})"
        )
    confirmed = sum(1 for r in rows if r["kind"] == "confirmed")
    print(f"\n확정 {confirmed}곳 / 추정 {len(rows) - confirmed}곳")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    json_path = Path(args.json)
    out_path = Path(args.out)

    if args.offline:
        if not json_path.exists():
            print(f"오류: {json_path}가 없습니다. --offline 없이 먼저 수집하세요.", file=sys.stderr)
            return 1
        services = _load(json_path)
        print(f"{json_path}에서 {len(services)}건을 읽었습니다.")
    else:
        print("서울시 공공서비스예약에서 테니스장 목록을 수집합니다…")
        try:
            collected: list[Service] = fetch_all(delay=args.delay, max_pages=args.max_pages)
        except FetchError as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 1
        services = [s.as_dict() for s in collected]
        _save(services, json_path)
        print(f"{len(services)}건을 {json_path}에 저장했습니다.")

    hist_path = Path(args.history)

    if args.details:
        print("상세 페이지에서 접수 시각을 읽습니다…")
        known = {r["svc_id"]: r for r in history.load(hist_path) if r.get("svc_id")}
        filled = _enrich_with_times(services, args.delay, known)
        print(f"  시각 {filled}건 새로 확보 (기록 재사용 {len(known)}건)")
        _save(services, json_path)

    fresh = history.observe(services, hist_path)
    if fresh:
        print(f"관찰 기록에 새 접수 건 {len(fresh)}건을 추가했습니다 → {hist_path}")

    if args.upcoming:
        _print_upcoming(history.load(hist_path), args.minutes)
        return 0

    out_path.write_text(render(services, dt.datetime.now()), encoding="utf-8")

    stats = summarize(services)
    print(f"HTML 생성: {out_path}")
    print(f"  접수중 {stats['open']}건 / 전체 {stats['total']}건")
    print(f"  지역 {len(stats['areas'])}곳, 장소 {len(stats['places'])}곳")
    if stats["range_start"]:
        print(f"  이용기간 {stats['range_start']} ~ {stats['range_end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""courtfinder 커맨드라인."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import __version__
from .fetch import FetchError, fetch_all
from .parser import Service
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
    return parser


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

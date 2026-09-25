"""목록 페이지 수집기.

공개된 검색 결과 페이지만 읽는다. 사이트가 봇 차단(dynaPath)을 걸어 둔
예약 달력 AJAX 엔드포인트는 건드리지 않는다.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Iterator

from .parser import Service, parse_page, parse_total

BASE = "https://yeyak.seoul.go.kr/web/search/selectPageListDetailSearchImg.do"
TENNIS = {"code": "T100", "dCode": "T108"}
PER_PAGE = 6
USER_AGENT = "courtfinder/0.1 (personal tennis court availability viewer)"


class FetchError(RuntimeError):
    """페이지를 가져오지 못했습니다."""


def fetch_page(page: int, timeout: int = 30, retries: int = 4) -> str:
    """한 페이지를 가져온다. 연결이 끊기면 간격을 늘려가며 다시 시도한다.

    재시도가 없으면 중간에 끊긴 페이지의 6건이 통째로 빠진다.
    """
    query = f"{BASE}?code={TENNIS['code']}&dCode={TENNIS['dCode']}&currentPage={page}"
    request = urllib.request.Request(query, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None

    for attempt in range(retries):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            last = exc

    raise FetchError(f"{page}페이지를 {retries}회 시도했으나 실패했습니다: {last}")


def _sweep(pages: int, delay: float, first_html: str,
           services: list[Service], seen: set[str]) -> list[int]:
    """1..pages를 훑어 새로 보이는 항목만 추가한다. 실패한 페이지 번호를 돌려준다."""
    failed: list[int] = []
    for page in range(1, pages + 1):
        if page > 1:
            time.sleep(delay)
        try:
            html = first_html if page == 1 and first_html else fetch_page(page)
        except FetchError as exc:
            failed.append(page)
            print(f"  ! {exc}", flush=True)
            continue
        for service in parse_page(html):
            if service.svc_id not in seen:
                seen.add(service.svc_id)
                services.append(service)
        if page % 15 == 0:
            print(f"  {page}/{pages} 페이지 — 누적 {len(services)}건", flush=True)

    return failed


def fetch_all(delay: float = 1.0, max_pages: int | None = None,
              progress: bool = True) -> list[Service]:
    """전체 목록을 순회한다.

    목록은 수집 도중에도 바뀐다(새 접수 건이 올라오면 뒤 페이지 항목이 밀린다).
    그래서 한 번 훑은 뒤 사이트 표기 건수에 못 미치면 한 번 더 훑어 빠진 항목을
    줍는다. 서버 부담을 줄이려 요청 사이에는 간격을 둔다.
    """
    first = fetch_page(1)
    total = parse_total(first)
    pages = (total + PER_PAGE - 1) // PER_PAGE
    if max_pages:
        pages = min(pages, max_pages)

    services: list[Service] = []
    seen: set[str] = set()
    failed = _sweep(pages, delay, first, services, seen)

    if not max_pages and (failed or len(services) < total):
        print(f"  1차 수집 {len(services)}건 / 사이트 표기 {total}건 — 빠진 항목을 다시 훑습니다")
        time.sleep(delay)
        failed = _sweep(pages, delay, "", services, seen)

    if failed:
        print(f"  경고: {len(failed)}개 페이지를 끝내 가져오지 못했습니다 {failed}")
        print(f"  사이트 표기 {total}건 중 {len(services)}건만 수집됐습니다.")
    elif len(services) < total:
        print(f"  참고: 사이트 표기 {total}건, 수집 {len(services)}건 "
              f"(수집 도중 목록이 바뀌면 몇 건 차이가 날 수 있습니다)")
    else:
        print(f"  {len(services)}건 전부 수집했습니다.")

    return services

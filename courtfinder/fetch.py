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


def fetch_page(page: int, timeout: int = 30) -> str:
    query = f"{BASE}?code={TENNIS['code']}&dCode={TENNIS['dCode']}&currentPage={page}"
    request = urllib.request.Request(query, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise FetchError(f"{page}페이지를 가져오지 못했습니다: {exc}") from exc


def fetch_all(delay: float = 1.0, max_pages: int | None = None,
              progress: bool = True) -> list[Service]:
    """전체 목록을 순회한다. 서버 부담을 줄이려 요청 사이에 간격을 둔다."""
    first = fetch_page(1)
    total = parse_total(first)
    pages = (total + PER_PAGE - 1) // PER_PAGE
    if max_pages:
        pages = min(pages, max_pages)

    services = list(parse_page(first))
    seen = {s.svc_id for s in services}

    for page in range(2, pages + 1):
        time.sleep(delay)
        try:
            html = fetch_page(page)
        except FetchError as exc:
            print(f"  건너뜀: {exc}")
            continue
        for service in parse_page(html):
            if service.svc_id not in seen:
                seen.add(service.svc_id)
                services.append(service)
        if progress:
            print(f"  {page}/{pages} 페이지 — 누적 {len(services)}건", flush=True)

    return services

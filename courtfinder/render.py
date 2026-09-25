"""수집한 서비스 목록을 날짜별로 조회 가능한 단독 HTML 파일로 만든다."""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "template.html"


def _date_span(service: dict) -> tuple[dt.date | None, dt.date | None]:
    def parse(value: str) -> dt.date | None:
        try:
            return dt.date.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    return parse(service.get("use_start", "")), parse(service.get("use_end", ""))


def summarize(services: list[dict]) -> dict:
    """페이지 상단에 띄울 집계와 필터 목록을 만든다."""
    areas = sorted({s["area"] for s in services if s["area"]})
    places = sorted({s["place"] for s in services if s["place"]})
    open_now = [s for s in services if s["status"] == "접수중"]

    starts = [d for d, _ in map(_date_span, services) if d]
    ends = [d for _, d in map(_date_span, services) if d]

    return {
        "total": len(services),
        "open": len(open_now),
        "areas": areas,
        "places": places,
        "range_start": min(starts).isoformat() if starts else "",
        "range_end": max(ends).isoformat() if ends else "",
    }


def render(services: list[dict], generated_at: dt.datetime | None = None) -> str:
    generated_at = generated_at or dt.datetime.now()
    payload = {
        "services": services,
        "summary": summarize(services),
        "generatedAt": generated_at.strftime("%Y-%m-%d %H:%M"),
    }
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return template.replace("/*__DATA__*/null", blob).replace(
        "__GENERATED_AT__", html.escape(payload["generatedAt"])
    )


def write(services: list[dict], destination: Path) -> Path:
    destination.write_text(render(services), encoding="utf-8")
    return destination

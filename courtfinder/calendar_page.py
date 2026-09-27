"""개방 캘린더 HTML 페이지를 만든다 (.ics 구독 안내 포함)."""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

from . import ics, predict

TEMPLATE_PATH = Path(__file__).parent / "calendar_template.html"

FEED_URL = (
    "https://raw.githubusercontent.com/suyong825-source/SYY/"
    "claude/what-can-we-do-here-qwhmlz/tennis-openings.ics"
)


def build_payload(records: list[dict], horizon_days: int = 100) -> dict:
    events = [
        {
            "place": e["place"],
            "area": e["area"],
            "at": e["opens_at"].strftime("%Y-%m-%dT%H:%M"),
            "kind": e["kind"],
            "cadence": e["cadence"],
            "rounds": e["rounds"],
            "lead": e["lead_days"],
            "span": e["span_days"],
            "url": e["url"],
        }
        for e in ics.series(records, horizon_days=horizon_days)
    ]

    patterns = []
    for (place, _time), group in predict.by_slot(records).items():
        pattern = predict.infer_pattern(group)
        patterns.append({
            "place": place,
            "area": group[0].get("area", ""),
            "cadence": pattern["cadence"],
            "label": predict.CADENCE_LABEL[pattern["cadence"]],
            "open_time": pattern["open_time"],
            "open_days": pattern["open_days"][:4],
            "span": pattern["span_days"],
            "lead": pattern["lead_days"],
            "rounds": pattern["rounds"],
            "schedulable": pattern["schedulable"],
        })

    return {"events": events, "patterns": patterns}


def render(records: list[dict], generated_at: dt.datetime | None = None,
           feed_url: str = FEED_URL, horizon_days: int = 100) -> str:
    generated_at = generated_at or dt.datetime.now(predict.KST)
    payload = build_payload(records, horizon_days)
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    return (
        TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("/*__DATA__*/null", blob)
        .replace("__GENERATED_AT__", html.escape(generated_at.strftime("%Y-%m-%d %H:%M")))
        .replace("__FEED_URL__", html.escape(feed_url))
    )

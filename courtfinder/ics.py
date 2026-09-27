"""접수 개방 일정을 iCalendar(.ics) 구독 파일로 내보낸다.

캘린더 앱이 URL로 구독하면 바탕화면·휴대폰 캘린더에 그대로 뜨고,
앱이 주기적으로 다시 받아가므로 파일만 갱신하면 일정도 따라 바뀐다.
각 일정에는 10분 전 알람(VALARM)을 넣어 캘린더 앱 자체가 알림을 띄우게 한다.
"""

from __future__ import annotations

import datetime as dt
import hashlib

from .predict import KST, _parse, alarm_time, by_slot, infer_pattern, predict_next

CAL_NAME = "서울 테니스장 예약 오픈"
CAL_DESC = "서울시 공공서비스예약 테니스장의 접수 개방 일정. 확정은 사이트 공고, 추정은 과거 패턴 계산값."

# 접수 개방은 한 시점의 사건이지만, 캘린더에서 너무 얇게 보이지 않도록 폭을 준다.
EVENT_MINUTES = 15


def _utc(stamp: dt.datetime) -> str:
    return stamp.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    """RFC 5545 텍스트 이스케이프."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """한 줄을 75옥텟 이하로 접는다. 한글이 잘리지 않도록 바이트 단위로 센다."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return [line]

    chunks, current, size = [], [], 0
    limit = 74  # 이어지는 줄은 앞에 공백 한 칸이 붙는다
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            chunks.append("".join(current))
            current, size, limit = [char], width, 73
        else:
            current.append(char)
            size += width
    chunks.append("".join(current))
    return [chunks[0]] + [" " + c for c in chunks[1:]]


def _uid(place: str, opens_at: dt.datetime) -> str:
    seed = f"{place}|{opens_at.isoformat()}".encode("utf-8")
    return f"{hashlib.sha1(seed).hexdigest()[:20]}@courtfinder.local"


def series(records: list[dict], now: dt.datetime | None = None,
           horizon_days: int = 90) -> list[dict]:
    """앞으로 horizon_days 동안의 개방 시점을 코트별로 여러 회차 뽑는다.

    사이트에 이미 올라온 미래 공고는 확정(confirmed)으로 그대로 쓰고,
    그 뒤로는 패턴을 굴려 추정(predicted)을 채운다.
    """
    now = now or dt.datetime.now(KST)
    limit = now + dt.timedelta(days=horizon_days)
    events: list[dict] = []

    for (place, _time), group in by_slot(records).items():
        pattern = infer_pattern(group)
        if not pattern.get("schedulable"):
            continue  # 상시·장기 접수는 '개방일'이라는 게 없다

        sample = group[0]
        confirmed = sorted(
            {o for o in (_parse(r.get("rcpt_open_at", "")) for r in group) if o and o > now}
        )
        taken = set()

        for opens_at in confirmed:
            if opens_at > limit:
                break
            events.append(_event(place, sample, pattern, opens_at, "confirmed"))
            taken.add(opens_at)

        cursor = max(confirmed) if confirmed else now
        guess = predict_next(pattern, cursor)
        while guess and guess <= limit:
            if guess not in taken:
                events.append(_event(place, sample, pattern, guess, "predicted"))
            guess = predict_next(pattern, guess)

    return sorted(events, key=lambda e: e["opens_at"])


def _event(place: str, sample: dict, pattern: dict,
           opens_at: dt.datetime, kind: str) -> dict:
    return {
        "place": place,
        "area": sample.get("area", ""),
        "opens_at": opens_at,
        "kind": kind,
        "cadence": pattern.get("cadence", "unknown"),
        "rounds": pattern.get("rounds", 0),
        "lead_days": pattern.get("lead_days"),
        "span_days": pattern.get("span_days"),
        "url": sample.get("url", ""),
    }


_CADENCE_KO = {"weekly": "주 단위", "half-monthly": "반달 단위", "monthly": "월 단위"}


def _describe(event: dict) -> str:
    lines = [
        f"{event['place']} ({event['area']})",
        f"접수 개방 {event['opens_at'].strftime('%Y-%m-%d %H:%M')} (KST)",
    ]
    cadence = _CADENCE_KO.get(event["cadence"], event["cadence"])
    span = f"{event['span_days']}일치" if event.get("span_days") else ""
    lines.append(f"주기: {cadence} {span}".rstrip())

    lead = event.get("lead_days")
    if lead is not None:
        if lead > 0:
            lines.append(f"이용 시작 {lead}일 전에 열립니다")
        elif lead == 0:
            lines.append("이용 시작 당일에 열립니다")

    if event["kind"] == "confirmed":
        lines.append("근거: 사이트에 올라온 공고 (확정)")
    else:
        lines.append(f"근거: 과거 {event['rounds']}회 관찰 패턴으로 계산한 추정 — 실제와 다를 수 있습니다")

    if event.get("url"):
        lines.append("")
        lines.append(event["url"])
    return "\n".join(lines)


def render(records: list[dict], now: dt.datetime | None = None,
           horizon_days: int = 90, minutes_before: int = 10) -> str:
    now = now or dt.datetime.now(KST)
    stamp = _utc(now)
    events = series(records, now=now, horizon_days=horizon_days)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//courtfinder//Seoul Tennis Openings//KO",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(CAL_NAME)}",
        f"X-WR-CALDESC:{_escape(CAL_DESC)}",
        "X-WR-TIMEZONE:Asia/Seoul",
        # 캘린더 앱에 재수집 주기를 권고한다 (앱마다 존중 정도가 다르다)
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]

    for event in events:
        opens_at = event["opens_at"]
        mark = "" if event["kind"] == "confirmed" else " (추정)"
        summary = f"🎾 {event['place']} 예약 오픈{mark}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{_uid(event['place'], opens_at)}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_utc(opens_at)}",
            f"DTEND:{_utc(opens_at + dt.timedelta(minutes=EVENT_MINUTES))}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape(_describe(event))}",
            f"LOCATION:{_escape(event['place'] + ' ' + event['area'])}",
            f"STATUS:{'CONFIRMED' if event['kind'] == 'confirmed' else 'TENTATIVE'}",
            f"CATEGORIES:{_escape('테니스장 접수')}",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"TRIGGER:-PT{minutes_before}M",
            "DESCRIPTION:" + _escape(
                f"{event['place']} 예약창이 {minutes_before}분 뒤 열립니다"
            ),
            "END:VALARM",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"


def summarize(records: list[dict], now: dt.datetime | None = None,
              horizon_days: int = 90) -> dict:
    events = series(records, now=now, horizon_days=horizon_days)
    return {
        "events": len(events),
        "confirmed": sum(1 for e in events if e["kind"] == "confirmed"),
        "places": len({e["place"] for e in events}),
        "first": events[0]["opens_at"].strftime("%Y-%m-%d %H:%M") if events else "",
        "last": events[-1]["opens_at"].strftime("%Y-%m-%d %H:%M") if events else "",
    }


def alarm_times(records: list[dict], minutes_before: int = 10,
                now: dt.datetime | None = None, horizon_days: int = 90) -> list[dt.datetime]:
    return [
        alarm_time(e["opens_at"].strftime("%Y-%m-%dT%H:%M"), minutes_before)
        for e in series(records, now=now, horizon_days=horizon_days)
    ]

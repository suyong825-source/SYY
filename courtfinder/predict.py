"""관찰 기록에서 코트별 접수 개방 패턴을 추론하고 다음 회차를 예측한다.

사이트 시각은 모두 한국 시간(KST)이다. 컨테이너가 어느 시간대에 있든
KST로 다루고, 알람을 걸 때만 UTC로 바꾼다.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 이용기간 길이로 회차 주기를 가른다
_HALF_MONTH = range(10, 20)   # 10~19일 → 반달 회차 (1~15일 / 16~31일)
_MONTHLY = range(25, 40)      # 25일 이상 → 월 단위 회차


def _parse(value: str) -> dt.datetime | None:
    """'2026-09-25T07:00' → KST datetime."""
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value).replace(tzinfo=KST)
    except ValueError:
        return None


def _parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def by_place(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        place = record.get("place")
        if place and record.get("rcpt_open_at"):
            grouped[place].append(record)
    return dict(grouped)


def infer_pattern(records: list[dict]) -> dict:
    """한 코트의 관찰 기록에서 개방 패턴을 뽑는다.

    표본이 적으면 적은 대로, 무엇을 몇 번 봤는지 함께 돌려준다.
    시각(몇 시)은 한 번만 봐도 꽤 믿을 만하지만, 날짜(며칠)는 회차가
    여러 번 쌓여야 확신할 수 있다.
    """
    opens = [_parse(r["rcpt_open_at"]) for r in records]
    opens = sorted({o for o in opens if o})
    if not opens:
        return {"samples": 0}

    times = Counter(o.strftime("%H:%M") for o in opens)
    days = Counter(o.day for o in opens)

    spans = []
    for record in records:
        start, end = _parse_date(record.get("use_start", "")), _parse_date(record.get("use_end", ""))
        if start and end and end >= start:
            spans.append((end - start).days + 1)

    cadence = "unknown"
    if spans:
        typical = Counter(spans).most_common(1)[0][0]
        if typical in _HALF_MONTH:
            cadence = "half-monthly"
        elif typical in _MONTHLY:
            cadence = "monthly"

    leads = []
    for record in records:
        opened, use_start = _parse(record["rcpt_open_at"]), _parse_date(record.get("use_start", ""))
        if opened and use_start:
            leads.append((use_start - opened.date()).days)

    # 회차(서로 다른 개방 일시)가 몇 번 관찰됐는지가 진짜 표본 수다
    rounds = len({o.strftime("%Y-%m-%d %H:%M") for o in opens})

    return {
        "samples": len(opens),
        "rounds": rounds,
        "open_time": times.most_common(1)[0][0],
        "open_time_counts": dict(times),
        "open_day": days.most_common(1)[0][0],
        "open_day_counts": dict(days),
        "cadence": cadence,
        "lead_days": Counter(leads).most_common(1)[0][0] if leads else None,
        "last_open": max(opens).strftime("%Y-%m-%dT%H:%M"),
        "confident": rounds >= 2 and cadence != "unknown",
    }


def _add_month(date: dt.date, months: int) -> dt.date:
    month = date.month - 1 + months
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
                         31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.date(year, month, day)


def predict_next(pattern: dict, after: dt.datetime) -> dt.datetime | None:
    """마지막 관찰 개방 시각에 주기를 더해 다음 개방 시각을 추정한다."""
    if not pattern.get("samples"):
        return None
    last = _parse(pattern["last_open"])
    if not last:
        return None

    cadence = pattern.get("cadence")
    if cadence == "monthly":
        step = lambda d: _add_month(d.date(), 1)
    elif cadence == "half-monthly":
        step = lambda d: d.date() + dt.timedelta(days=15)
    else:
        return None

    candidate = last
    for _ in range(24):  # 최대 2년치까지만 굴린다
        next_date = step(candidate)
        candidate = dt.datetime.combine(next_date, last.timetz())
        if candidate > after:
            return candidate
    return None


def upcoming(records: list[dict], now: dt.datetime | None = None,
             horizon_days: int = 45) -> list[dict]:
    """코트별 '다음 개방'을 모은다.

    사이트에 이미 올라온 미래 접수 건이 있으면 그 시각을 그대로 쓰고(confirmed),
    없으면 패턴으로 추정한다(predicted). 추정치는 그렇다고 표시한다.
    """
    now = now or dt.datetime.now(KST)
    limit = now + dt.timedelta(days=horizon_days)
    results = []

    for place, group in sorted(by_place(records).items()):
        pattern = infer_pattern(group)

        future = sorted(
            (o for o in (_parse(r["rcpt_open_at"]) for r in group) if o and o > now)
        )
        if future:
            opens_at, kind = future[0], "confirmed"
        else:
            guess = predict_next(pattern, now)
            if not guess or guess > limit:
                continue
            opens_at, kind = guess, "predicted"

        if opens_at > limit:
            continue

        sample = next(
            (r for r in group if _parse(r.get("rcpt_open_at", "")) == opens_at),
            group[0],
        )
        results.append({
            "place": place,
            "area": sample.get("area", ""),
            "opens_at": opens_at.strftime("%Y-%m-%dT%H:%M"),
            "kind": kind,
            "cadence": pattern.get("cadence", "unknown"),
            "rounds_seen": pattern.get("rounds", 0),
            "confident": pattern.get("confident", False),
            "use_start": sample.get("use_start", ""),
            "use_end": sample.get("use_end", ""),
            "example_title": sample.get("title", ""),
        })

    return sorted(results, key=lambda r: r["opens_at"])


def alarm_time(opens_at: str, minutes_before: int = 10) -> dt.datetime:
    """개방 N분 전의 KST 시각."""
    return _parse(opens_at) - dt.timedelta(minutes=minutes_before)


def alarm_message(entry: dict, minutes_before: int = 10) -> str:
    opens = _parse(entry["opens_at"])
    window = ""
    if entry.get("use_start") and entry.get("use_end"):
        window = f" (이용기간 {entry['use_start'][5:].replace('-', '/')}~{entry['use_end'][5:].replace('-', '/')})"
    hedge = "" if entry["kind"] == "confirmed" else " ※ 과거 패턴 기반 추정입니다"
    return (
        f"{entry['place']}({entry['area']}) 예약창이 {minutes_before}분 뒤 "
        f"{opens.strftime('%H:%M')}에 열립니다{window}.{hedge}"
    )

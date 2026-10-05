"""이메일 텍스트에서 항공편 정보를 파싱한다. 순수 함수만."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date


@dataclass
class FlightLeg:
    flight_no: str    # "KE703" — 없으면 빈 문자열
    origin: str       # "ICN"
    dest: str         # "NRT"
    depart: datetime  # naive, 출발지 로컬 시각
    arrive: datetime  # naive, 도착지 로컬 시각


# ── 기본 패턴 ────────────────────────────────────────────────

_IATA = r"[A-Z]{3}"
_TIME = r"(\d{1,2}):(\d{2})"
_FLIGHT_NO = r"\b([A-Z0-9]{2,3}\s?\d{1,4})\b"

# 날짜 형식: "2026년 10월 15일", "2026-10-15", "Oct 15, 2026", "15 Oct 2026"
_KO_DATE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_EN_DATE = re.compile(
    r"(?:(\d{1,2})\s+)?([A-Z][a-z]{2})\s+(\d{1,2})(?:,?\s+(\d{4}))?",
    re.IGNORECASE,
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 출발 → 도착 구분자: "→", "->", "►", ">", "▶"
_SEP = re.compile(r"→|->|►|▶|>")

# "공항명(ICN)" 또는 "(ICN)" 형식
_IATA_IN_PAREN = re.compile(r"\(([A-Z]{3})\)")


def _parse_date(text: str, year_hint: int | None = None) -> date | None:
    m = _KO_DATE.search(text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _ISO_DATE.search(text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _EN_DATE.search(text)
    if m:
        mon = _MONTHS.get(m.group(2)[:3].lower())
        if mon:
            day = int(m.group(3) if m.group(1) is None else m.group(1) or m.group(3))
            yr = int(m.group(4)) if m.group(4) else (year_hint or datetime.now().year)
            try:
                return date(yr, mon, day)
            except ValueError:
                pass
    return None


def _parse_time(text: str) -> tuple[int, int] | None:
    m = re.search(_TIME, text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _find_iata_codes(text: str) -> list[str]:
    """텍스트에서 공항 IATA 코드를 순서대로 뽑는다."""
    # 괄호 안 코드 우선
    codes = _IATA_IN_PAREN.findall(text)
    if not codes:
        # 띄어쓰기로 구분된 대문자 3글자
        codes = re.findall(r"\b([A-Z]{3})\b", text)
    return codes


def _find_flight_no(text: str) -> str:
    m = re.search(_FLIGHT_NO, text)
    return m.group(1).replace(" ", "") if m else ""


def parse_email(subject: str, body: str) -> list[FlightLeg]:
    """이메일 제목+본문에서 항공편 목록을 추출한다."""
    full = subject + "\n" + body
    legs: list[FlightLeg] = []

    # 날짜 후보 수집
    dates: list[date] = []
    for m in _KO_DATE.finditer(full):
        dates.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _ISO_DATE.finditer(full):
        dates.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    year_hint = dates[0].year if dates else None

    # 줄 단위 또는 "→" 구분 구간을 순회하며 출발/도착 쌍 탐색
    segments = _SEP.split(full)
    if len(segments) < 2:
        # 구분자 없으면 전체를 하나의 덩어리로
        segments = [full]

    # 구분자가 있을 때: segments[i] = 출발 정보, segments[i+1] = 도착 정보
    if len(segments) >= 2:
        for i in range(len(segments) - 1):
            dep_block = segments[i]
            arr_block = segments[i + 1]

            dep_codes = _find_iata_codes(dep_block[-80:])  # 뒤쪽에 출발 코드
            arr_codes = _find_iata_codes(arr_block[:80])   # 앞쪽에 도착 코드
            if not dep_codes or not arr_codes:
                continue

            origin = dep_codes[-1]
            dest = arr_codes[0]
            if origin == dest:
                continue

            # 시각
            dep_time = _parse_time(dep_block[-120:])
            arr_time = _parse_time(arr_block[:120])
            if not dep_time or not arr_time:
                continue

            # 날짜: 블록에 있으면 그걸 쓰고, 없으면 수집한 날짜 목록 순서대로
            dep_date = _parse_date(dep_block, year_hint) or (dates[len(legs)] if len(legs) < len(dates) else None)
            arr_date = _parse_date(arr_block, year_hint) or dep_date
            if not dep_date or not arr_date:
                continue

            flight_no = _find_flight_no(dep_block[-200:] + arr_block[:200])

            legs.append(FlightLeg(
                flight_no=flight_no,
                origin=origin,
                dest=dest,
                depart=datetime(dep_date.year, dep_date.month, dep_date.day, *dep_time),
                arrive=datetime(arr_date.year, arr_date.month, arr_date.day, *arr_time),
            ))

    return _dedupe(legs)


def _dedupe(legs: list[FlightLeg]) -> list[FlightLeg]:
    seen: set[tuple] = set()
    out = []
    for leg in legs:
        key = (leg.origin, leg.dest, leg.depart)
        if key not in seen:
            seen.add(key)
            out.append(leg)
    return out

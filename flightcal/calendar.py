"""Google 캘린더에 항공편 이벤트를 현지 시각 기준으로 등록한다."""

from __future__ import annotations

from dataclasses import dataclass

from googleapiclient.discovery import build

from . import airports
from .auth import get_credentials
from .parse import FlightLeg

_CAL_ID = "primary"


@dataclass
class SyncResult:
    leg: FlightLeg
    event_id: str
    html_link: str
    skipped: bool = False   # 이미 존재하는 이벤트면 True


def _event_body(leg: FlightLeg, origin_tz: str, dest_tz: str) -> dict:
    label = leg.flight_no or f"{leg.origin}→{leg.dest}"
    summary = f"✈ {label} {leg.origin}→{leg.dest}"
    description = (
        f"출발: {leg.origin} ({airports.name(leg.origin)}) {leg.depart.strftime('%H:%M')} {origin_tz}\n"
        f"도착: {leg.dest} ({airports.name(leg.dest)}) {leg.arrive.strftime('%H:%M')} {dest_tz}"
    )
    return {
        "summary": summary,
        "description": description,
        # 핵심: 출발은 출발지 시간대, 도착은 도착지 시간대로 각각 지정
        "start": {
            "dateTime": leg.depart.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": origin_tz,
        },
        "end": {
            "dateTime": leg.arrive.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": dest_tz,
        },
        "source": {
            "title": "flightcal",
            "url": "https://github.com/suyong825-source/SYY",
        },
    }


def _already_exists(service, leg: FlightLeg, origin_tz: str) -> str | None:
    """같은 출발지·시각의 이벤트가 이미 있으면 eventId를 반환한다."""
    from zoneinfo import ZoneInfo

    aware = leg.depart.replace(tzinfo=ZoneInfo(origin_tz))
    time_min = aware.isoformat()
    result = service.events().list(
        calendarId=_CAL_ID,
        timeMin=time_min,
        timeMax=time_min,  # 정확히 같은 시각
        singleEvents=True,
        q=leg.origin,
    ).execute()
    for ev in result.get("items", []):
        if leg.dest in ev.get("summary", ""):
            return ev["id"]
    return None


def sync_legs(legs: list[FlightLeg]) -> list[SyncResult]:
    """항공편 목록을 Google 캘린더에 등록하고 결과를 반환한다."""
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    results: list[SyncResult] = []

    for leg in legs:
        try:
            origin_tz = airports.timezone(leg.origin)
            dest_tz = airports.timezone(leg.dest)
        except KeyError as e:
            print(f"  알 수 없는 공항 코드 건너뜀: {e}")
            continue

        existing = _already_exists(service, leg, origin_tz)
        if existing:
            results.append(SyncResult(
                leg=leg, event_id=existing,
                html_link=f"https://calendar.google.com/calendar/r/eventedit/{existing}",
                skipped=True,
            ))
            continue

        body = _event_body(leg, origin_tz, dest_tz)
        event = service.events().insert(calendarId=_CAL_ID, body=body).execute()
        results.append(SyncResult(
            leg=leg,
            event_id=event["id"],
            html_link=event.get("htmlLink", ""),
        ))

    return results

"""flightcal 파서 테스트 — 실제 API 불필요."""

from datetime import datetime

from flightcal.parse import parse_email


# ── 대한항공 스타일 한국어 이메일 ─────────────────────────────

KE_EMAIL = """
대한항공 전자항공권 안내

항공편: KE703
출발: 인천(ICN) 2026년 10월 15일 09:30
→ 도착: 나리타(NRT) 2026년 10월 15일 11:30
"""


def test_ke_korean_style():
    legs = parse_email("대한항공 전자항공권", KE_EMAIL)
    assert len(legs) == 1
    leg = legs[0]
    assert leg.origin == "ICN"
    assert leg.dest == "NRT"
    assert leg.depart == datetime(2026, 10, 15, 9, 30)
    assert leg.arrive == datetime(2026, 10, 15, 11, 30)
    assert "KE703" in leg.flight_no or leg.flight_no == "KE703"


# ── 왕복 항공편 ──────────────────────────────────────────────

ROUND_TRIP = """
Your itinerary

Outbound
ICN 2026-10-15 09:30 → NRT 2026-10-15 11:30
Flight OZ101

Return
NRT 2026-10-22 13:00 → ICN 2026-10-22 15:30
Flight OZ102
"""


def test_round_trip_extracts_two_legs():
    legs = parse_email("Flight confirmation", ROUND_TRIP)
    assert len(legs) == 2
    origins = {leg.origin for leg in legs}
    assert origins == {"ICN", "NRT"}


# ── 알 수 없는 공항 코드가 있어도 나머지 파싱 성공 ─────────────

MIXED = """
OZ101
인천(ICN) 09:30 → 나리타(NRT) 11:30
2026-10-15
"""


def test_iso_date_format():
    legs = parse_email("", MIXED)
    assert len(legs) >= 1
    assert legs[0].depart.date().isoformat() == "2026-10-15"


# ── airports 모듈 ─────────────────────────────────────────────

def test_airports_timezone_known():
    from flightcal.airports import timezone
    assert timezone("ICN") == "Asia/Seoul"
    assert timezone("NRT") == "Asia/Tokyo"
    assert timezone("LHR") == "Europe/London"
    assert timezone("JFK") == "America/New_York"


def test_airports_timezone_case_insensitive():
    from flightcal.airports import timezone
    assert timezone("icn") == timezone("ICN")


def test_airports_unknown_raises():
    from flightcal.airports import timezone
    import pytest
    with pytest.raises(KeyError):
        timezone("ZZZ")

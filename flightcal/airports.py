"""IATA 공항 코드 → 시간대 조회."""

from __future__ import annotations

import functools

import airportsdata


@functools.cache
def _db() -> dict:
    return airportsdata.load("IATA")


def timezone(iata: str) -> str:
    """IATA 코드로 시간대 문자열을 반환한다. 알 수 없으면 KeyError."""
    entry = _db().get(iata.upper())
    if entry and entry.get("tz"):
        return entry["tz"]
    raise KeyError(iata)


def name(iata: str) -> str:
    """공항 이름을 반환한다. 알 수 없으면 코드 그대로."""
    entry = _db().get(iata.upper())
    return entry["name"] if entry else iata

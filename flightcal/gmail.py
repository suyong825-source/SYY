"""Gmail에서 항공권 관련 이메일을 가져온다."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from googleapiclient.discovery import build

from .auth import get_credentials

# 항공권 이메일에 자주 등장하는 키워드 (한/영)
_QUERY = (
    "subject:(항공 OR 비행 OR flight OR boarding OR 탑승 OR ticket OR e-ticket"
    " OR 여행 예약 OR itinerary OR reservation)"
)


@dataclass
class RawEmail:
    msg_id: str
    subject: str
    body: str


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime in ("text/plain", "text/html"):
        data = payload.get("body", {}).get("data", "")
        text = _decode_part(data)
        if mime == "text/html":
            text = re.sub(r"<[^>]+>", " ", text)
        return text
    parts = payload.get("parts", [])
    # text/plain 우선, 없으면 첫 번째 파트
    for p in parts:
        if p.get("mimeType") == "text/plain":
            return _extract_body(p)
    for p in parts:
        result = _extract_body(p)
        if result.strip():
            return result
    return ""


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch_flight_emails(since_days: int = 60) -> list[RawEmail]:
    """최근 since_days일 내 항공권 이메일을 반환한다."""
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    query = f"{_QUERY} newer_than:{since_days}d"
    result = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    messages = result.get("messages", [])

    emails: list[RawEmail] = []
    for msg in messages:
        full = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()
        payload = full.get("payload", {})
        headers = payload.get("headers", [])
        subject = _header(headers, "Subject")
        body = _extract_body(payload)
        emails.append(RawEmail(msg_id=msg["id"], subject=subject, body=body))

    return emails

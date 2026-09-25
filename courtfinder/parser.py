"""서울 공공서비스예약 테니스장 목록 페이지 파서.

네트워크를 타지 않는 순수 함수만 둔다 — 저장해 둔 HTML로 테스트할 수 있게.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, asdict

CARD_RE = re.compile(r"fnDetailPage\('([^']+)'", re.S)
TOTAL_RE = re.compile(r'총\s*<span class="text_red">([\d,]+)</span>\s*건')

_STATUS_RE = re.compile(r'<span class="bd_label status\d">\s*([^<]+?)\s*</span>')
_TYPE_RE = re.compile(r'<span class="bd_label type\d">\s*(.*?)\s*</span>', re.S)
_TITLE_RE = re.compile(r'<h3 class="tit1 sch-rslt">\s*(.*?)\s*</h3>', re.S)
_PLACE_RE = re.compile(r'<b class="place">장소명</b>\s*<div[^>]*>\s*(.*?)\s*</div>', re.S)
_TARGET_RE = re.compile(r'<b class="user">이용대상</b>\s*<div[^>]*>\s*(.*?)\s*</div>', re.S)
_RCPT_RE = re.compile(r'<b class="date1">접수기간</b>\s*([\d.]{10})\s*~\s*([\d.]{10})')
_USE_RE = re.compile(r'<b class="date2">이용기간</b>\s*([\d.]{10})\s*~\s*([\d.]{10})')
_AREA_RE = re.compile(r'\(([^()]*[구군시])\)\s*$')

_TIME_RE = re.compile(r'(\d{1,2})\s*시\s*[~\-]\s*(\d{1,2})\s*시')
_TIME_COLON_RE = re.compile(r'(\d{1,2}):(\d{2})\s*[~\-]\s*(\d{1,2}):(\d{2})')
# '3번코트', 'A코트', '5번 코트', 'A면', '3면' 등 표기가 뒤섞여 있다.
_COURT_RE = re.compile(r'([A-Za-z]|\d{1,2})\s*(번)?\s*(코트|면)')

# 제목에 시계 시간 대신 쓰이는 시간대 표현들
_SLOT_WORDS = (
    ("새벽", "새벽"),
    ("야간", "야간"),
    ("저녁", "야간"),
    ("나이트", "야간"),
    ("라이트", "야간"),
    ("조명", "야간"),
    ("주간", "주간"),
    ("오전", "주간"),
    ("오후", "주간"),
)


def _text(raw: str) -> str:
    """태그를 걷어내고 공백을 한 칸으로 정리한다."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _iso(korean_date: str) -> str:
    """'2026.10.01' -> '2026-10-01'."""
    return korean_date.strip().replace(".", "-")


@dataclass
class Service:
    svc_id: str
    title: str
    place: str
    area: str
    status: str
    paid: str
    target: str
    rcpt_start: str
    rcpt_end: str
    use_start: str
    use_end: str
    court: str
    holiday_ok: bool
    slot: str
    time_start: str
    time_end: str
    day_type: str
    url: str

    def as_dict(self) -> dict:
        return asdict(self)


def parse_total(page_html: str) -> int:
    match = TOTAL_RE.search(page_html)
    return int(match.group(1).replace(",", "")) if match else 0


def _split_cards(page_html: str) -> list[str]:
    """카드 목록을 잘라낸다.

    `<ul class="img_board">` 안에 `<ul>`이 중첩되어 있어 닫는 태그로는 경계를 잡을 수
    없다. 목록 시작점부터 카드 앵커를 기준으로 쪼갠다.
    """
    start = page_html.find('<ul class="img_board">')
    body = page_html[start:] if start >= 0 else page_html
    chunks = re.split(r'(?=<a href="#" onclick="fnDetailPage)', body)
    return [c for c in chunks if "fnDetailPage" in c]


def parse_time(title: str) -> tuple[str, str]:
    """제목에서 이용 시간대를 뽑는다. 못 찾으면 빈 문자열."""
    colon = _TIME_COLON_RE.search(title)
    if colon:
        return (
            f"{int(colon.group(1)):02d}:{colon.group(2)}",
            f"{int(colon.group(3)):02d}:{colon.group(4)}",
        )
    hour = _TIME_RE.search(title)
    if hour:
        return f"{int(hour.group(1)):02d}:00", f"{int(hour.group(2)):02d}:00"
    return "", ""


def parse_court(title: str) -> str:
    """'3번코트', 'A코트', 'A면' 같은 표기를 하나의 라벨로 정리한다."""
    match = _COURT_RE.search(title)
    if not match:
        return ""
    name, unit = match.group(1).upper(), match.group(3)
    if name.isdigit():
        # '3번코트'는 번을 붙여 읽고, '3면'은 그대로가 자연스럽다
        return f"{int(name)}번코트" if unit == "코트" else f"{int(name)}면"
    return f"{name}{unit}"


def parse_slot(title: str, time_start: str = "") -> str:
    """시간대 구분. 제목의 표현을 우선 보고, 없으면 시계 시간으로 가른다.

    서울시 테니스장 제목에는 '17시~19시'보다 '야간', '저녁', '라이트' 같은 말이
    훨씬 자주 쓰인다.
    """
    found = []
    for word, label in _SLOT_WORDS:
        if word in title and label not in found:
            found.append(label)
    if found:
        order = {"새벽": 0, "주간": 1, "야간": 2}
        return "·".join(sorted(found, key=lambda x: order.get(x, 9)))
    if time_start:
        hour = int(time_start[:2])
        if hour < 7:
            return "새벽"
        return "야간" if hour >= 17 else "주간"
    return ""


def mentions_holiday(title: str) -> bool:
    """제목이 공휴일을 명시하는지. '주말 및 공휴일', '토/일/공휴일' 등."""
    return any(w in title for w in ("공휴", "휴일"))


def parse_day_type(title: str) -> str:
    """평일/주말 구분. 제목에 단서가 없으면 '전체'."""
    has_weekday = "평일" in title
    has_weekend = any(w in title for w in ("주말", "토일", "휴일", "토/일", "공휴"))
    if has_weekday and not has_weekend:
        return "평일"
    if has_weekend and not has_weekday:
        return "주말"
    return "전체"


def parse_card(card_html: str) -> Service | None:
    id_match = CARD_RE.search(card_html)
    title_match = _TITLE_RE.search(card_html)
    if not id_match or not title_match:
        return None

    title = _text(title_match.group(1))
    place_raw = _text(_PLACE_RE.search(card_html).group(1)) if _PLACE_RE.search(card_html) else ""
    area_match = _AREA_RE.search(place_raw)
    area = area_match.group(1) if area_match else ""
    place = _AREA_RE.sub("", place_raw).strip() if area else place_raw

    rcpt = _RCPT_RE.search(card_html)
    use = _USE_RE.search(card_html)
    status = _STATUS_RE.search(card_html)
    paid = _TYPE_RE.search(card_html)
    target = _TARGET_RE.search(card_html)
    time_start, time_end = parse_time(title)
    svc_id = id_match.group(1)

    return Service(
        svc_id=svc_id,
        title=title,
        place=place,
        area=area,
        status=_text(status.group(1)) if status else "",
        paid=_text(paid.group(1)) if paid else "",
        target=_text(target.group(1)) if target else "",
        rcpt_start=_iso(rcpt.group(1)) if rcpt else "",
        rcpt_end=_iso(rcpt.group(2)) if rcpt else "",
        use_start=_iso(use.group(1)) if use else "",
        use_end=_iso(use.group(2)) if use else "",
        court=parse_court(title),
        holiday_ok=mentions_holiday(title),
        slot=parse_slot(title, time_start),
        time_start=time_start,
        time_end=time_end,
        day_type=parse_day_type(title),
        url=f"https://yeyak.seoul.go.kr/web/reservation/selectReservView.do?rsv_svc_id={svc_id}",
    )


def parse_page(page_html: str) -> list[Service]:
    services = []
    for card in _split_cards(page_html):
        service = parse_card(card)
        if service:
            services.append(service)
    return services

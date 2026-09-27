import datetime as dt

from courtfinder import parser, render

CARD = """
<ul class="img_board">
<li>
<a href="#" onclick="fnDetailPage('S260917110259954206', '', ''); return false;" title="x">
<div class="img_box"><div class="ib_top">
<span class="bd_label status1">접수중</span>
<span class="bd_label type1">유료</span>
</div></div>
<div class="con_box">
<h3 class="tit1 sch-rslt">신도림테니스장 10월 평일 C코트 야간 접수(17시~19시 ) </h3>
<ul class="ib_attr">
<li><b class="place">장소명</b> <div class="sch-rslt txt2 card-line">신도림테니스장(구로구)</div></li>
<li><b class="user">이용대상</b> <div class="txt2 card-line">제한없음</div></li>
<li><b class="date1">접수기간</b> 2026.09.25 ~ 2026.10.31</li>
<li><b class="date2">이용기간</b> 2026.10.01 ~ 2026.10.31</li>
</ul>
</div></a></li>
</ul>
"""


def test_parse_card_extracts_all_fields():
    svc = parser.parse_page(CARD)[0]
    assert svc.svc_id == "S260917110259954206"
    assert svc.place == "신도림테니스장"
    assert svc.area == "구로구"
    assert svc.status == "접수중"
    assert svc.paid == "유료"
    assert svc.court == "C코트"
    assert svc.time_start == "17:00"
    assert svc.time_end == "19:00"
    assert svc.day_type == "평일"
    assert svc.use_start == "2026-10-01"
    assert svc.rcpt_end == "2026-10-31"
    assert svc.svc_id in svc.url


def test_parse_total():
    assert parser.parse_total('총 <span class="text_red">359</span> 건') == 359
    assert parser.parse_total("no count here") == 0


def test_parse_time_handles_colon_form():
    assert parser.parse_time("A코트 09:30~11:30") == ("09:30", "11:30")
    assert parser.parse_time("시간 없음") == ("", "")


def test_parse_time_pads_single_digit_hours():
    assert parser.parse_time("주간 7시~9시") == ("07:00", "09:00")


def test_day_type_prefers_explicit_weekday():
    assert parser.parse_day_type("평일 주간") == "평일"
    assert parser.parse_day_type("주말 야간") == "주말"
    assert parser.parse_day_type("토일 포함") == "주말"
    assert parser.parse_day_type("10월 A코트") == "전체"
    # 평일과 주말이 모두 적힌 제목은 한쪽으로 단정하지 않는다
    assert parser.parse_day_type("평일/주말 통합") == "전체"


def test_parse_court_uppercases():
    assert parser.parse_court("신도림 b코트 야간") == "B코트"
    assert parser.parse_court("코트 표기 없음") == ""


def test_summarize_counts_open_and_span():
    services = [
        {"area": "구로구", "place": "신도림", "status": "접수중",
         "use_start": "2026-10-01", "use_end": "2026-10-31"},
        {"area": "서대문구", "place": "가좌", "status": "접수마감",
         "use_start": "2026-09-01", "use_end": "2026-09-30"},
    ]
    stats = render.summarize(services)
    assert stats["total"] == 2
    assert stats["open"] == 1
    assert stats["areas"] == ["구로구", "서대문구"]
    assert stats["range_start"] == "2026-09-01"
    assert stats["range_end"] == "2026-10-31"


def test_summarize_survives_missing_dates():
    stats = render.summarize([{"area": "", "place": "", "status": "",
                               "use_start": "", "use_end": ""}])
    assert stats["range_start"] == ""


def test_render_embeds_data_and_closes_script_safely():
    services = [{"area": "구로구", "place": "신도림", "status": "접수중",
                 "use_start": "2026-10-01", "use_end": "2026-10-31",
                 "title": "</script> 주입 시도", "court": "A코트",
                 "time_start": "07:00", "time_end": "09:00", "day_type": "평일",
                 "svc_id": "S1", "url": "https://example.test", "paid": "유료",
                 "target": "제한없음", "rcpt_start": "2026-09-01", "rcpt_end": "2026-10-31"}]
    out = render.render(services, dt.datetime(2026, 9, 25, 12, 0))
    assert "2026-09-25 12:00" in out
    assert "신도림" in out
    # 데이터에 들어온 </script>가 스크립트 블록을 끊지 못해야 한다
    assert "</script> 주입" not in out
    assert "<\\/script>" in out


def test_parse_court_handles_numbered_and_myeon_forms():
    assert parser.parse_court("장충테니스장 3번코트(주말)") == "3번코트"
    assert parser.parse_court("월드컵공원 테니스장 A면 (주말)") == "A면"
    assert parser.parse_court("마루공원 테니스장 3면 (조명)") == "3면"
    assert parser.parse_court("한남테니스장 12번코트 평일") == "12번코트"
    assert parser.parse_court("삼청테니스장 코트이용(평일)") == ""


def test_parse_slot_reads_korean_time_words():
    assert parser.parse_slot("삼청테니스장 코트이용(야간)") == "야간"
    assert parser.parse_slot("망원 한강공원 테니스장 2번 코트 저녁") == "야간"
    assert parser.parse_slot("마루공원 테니스장 3면 (조명)") == "야간"
    assert parser.parse_slot("한남테니스장 12번코트 평일 새벽,주간") == "새벽·주간"
    assert parser.parse_slot("코트 이용") == ""


def test_parse_slot_falls_back_to_clock_time():
    assert parser.parse_slot("코트 이용", "19:00") == "야간"
    assert parser.parse_slot("코트 이용", "09:00") == "주간"
    assert parser.parse_slot("코트 이용", "05:00") == "새벽"


def test_day_type_treats_holiday_as_weekend():
    assert parser.parse_day_type("장충테니스장 3번코트(주말 및 공휴일)") == "주말"
    assert parser.parse_day_type("테니스장2(토/일/공휴일)-응봉공원") == "주말"


def test_mentions_holiday():
    assert parser.mentions_holiday("장충테니스장 3번코트(주말 및 공휴일)")
    assert parser.mentions_holiday("테니스장2(토/일/공휴일)")
    assert not parser.mentions_holiday("9월_월곡테니스장 3번 코트(주말)")


def test_holiday_table_marks_rest_days():
    import datetime as dt

    from courtfinder import holidays

    # 2026-09-25는 금요일이지만 추석이다
    chuseok = dt.date(2026, 9, 25)
    assert chuseok.weekday() == 4
    assert holidays.is_holiday(chuseok)
    assert holidays.is_rest_day(chuseok)
    assert holidays.holiday_name(chuseok) == "추석"

    # 평범한 화요일
    plain = dt.date(2026, 10, 6)
    assert not holidays.is_holiday(plain)
    assert not holidays.is_rest_day(plain)

    # 토요일은 공휴일이 아니어도 휴일 일정
    assert holidays.is_rest_day(dt.date(2026, 10, 10))


def test_holidays_are_embedded_in_page():
    out = render.render([], dt.datetime(2026, 9, 25, 9, 0))
    assert "2026-09-25" in out
    assert "추석" in out


# ── 개방 패턴 학습·예측 ────────────────────────────────────────
def _rec(place, open_at, use_start, use_end, svc_id="S1"):
    return {"svc_id": svc_id, "place": place, "area": "종로구", "title": place,
            "status": "안내중", "rcpt_open_at": open_at, "rcpt_close_at": "",
            "use_start": use_start, "use_end": use_end}


def test_observe_appends_only_new_services(tmp_path):
    from courtfinder import history

    path = tmp_path / "h.jsonl"
    first = history.observe([_rec("삼청", "2026-09-25T07:00", "2026-10-01", "2026-10-31", "A")], path)
    assert len(first) == 1

    again = history.observe([_rec("삼청", "2026-09-25T07:00", "2026-10-01", "2026-10-31", "A")], path)
    assert again == []

    added = history.observe([_rec("장충", "2026-09-25T10:00", "2026-10-01", "2026-10-15", "B")], path)
    assert len(added) == 1
    assert len(history.load(path)) == 2


def test_history_survives_a_corrupt_line(tmp_path):
    from courtfinder import history

    path = tmp_path / "h.jsonl"
    path.write_text('{"svc_id": "A"}\nnot json\n{"svc_id": "B"}\n', encoding="utf-8")
    assert [r["svc_id"] for r in history.load(path)] == ["A", "B"]


def test_infer_pattern_reads_time_and_cadence():
    from courtfinder import predict

    records = [
        _rec("신도림", "2026-08-25T07:00", "2026-09-01", "2026-09-30"),
        _rec("신도림", "2026-09-25T07:00", "2026-10-01", "2026-10-31"),
    ]
    pattern = predict.infer_pattern(records)
    assert pattern["open_time"] == "07:00"
    assert pattern["open_day"] == 25
    assert pattern["cadence"] == "monthly"
    assert pattern["rounds"] == 2
    assert pattern["confident"] is True


def test_single_round_is_not_confident():
    from courtfinder import predict

    pattern = predict.infer_pattern([_rec("삼청", "2026-09-25T07:00", "2026-10-01", "2026-10-31")])
    assert pattern["rounds"] == 1
    assert pattern["confident"] is False


def test_half_month_cadence_detected():
    from courtfinder import predict

    records = [
        _rec("가좌", "2026-09-10T00:00", "2026-09-16", "2026-09-30"),
        _rec("가좌", "2026-09-25T00:00", "2026-10-01", "2026-10-15"),
    ]
    assert predict.infer_pattern(records)["cadence"] == "half-monthly"


def test_predict_next_adds_one_month():
    import datetime as dtm

    from courtfinder import predict

    records = [
        _rec("신도림", "2026-08-25T07:00", "2026-09-01", "2026-09-30"),
        _rec("신도림", "2026-09-25T07:00", "2026-10-01", "2026-10-31"),
    ]
    pattern = predict.infer_pattern(records)
    now = dtm.datetime(2026, 9, 26, 12, 0, tzinfo=predict.KST)
    nxt = predict.predict_next(pattern, now)
    assert nxt.strftime("%Y-%m-%d %H:%M") == "2026-10-25 07:00"


def test_standing_reservations_are_not_scheduled():
    import datetime as dtm

    from courtfinder import predict

    # 이용기간이 1년짜리면 '다음 회차'라는 개념이 없다
    pattern = predict.infer_pattern([_rec("탄천", "2026-09-25T14:00", "2026-01-01", "2026-12-31")])
    assert pattern["cadence"] == "standing"
    assert pattern["schedulable"] is False
    assert predict.predict_next(pattern, dtm.datetime(2026, 9, 26, tzinfo=predict.KST)) is None


def test_weekly_cadence_steps_seven_days():
    import datetime as dtm

    from courtfinder import predict

    records = [
        _rec("난우", "2026-09-02T15:00", "2026-09-07", "2026-09-13"),
        _rec("난우", "2026-09-09T15:00", "2026-09-14", "2026-09-20"),
    ]
    pattern = predict.infer_pattern(records)
    assert pattern["cadence"] == "weekly"
    nxt = predict.predict_next(pattern, dtm.datetime(2026, 9, 10, tzinfo=predict.KST))
    assert nxt.strftime("%Y-%m-%d %H:%M") == "2026-09-16 15:00"


def test_upcoming_prefers_confirmed_over_predicted():
    import datetime as dtm

    from courtfinder import predict

    records = [
        _rec("삼청", "2026-08-20T06:00", "2026-09-01", "2026-09-30", "A"),
        _rec("삼청", "2026-10-20T06:00", "2026-11-01", "2026-11-30", "B"),
    ]
    now = dtm.datetime(2026, 9, 25, 12, 0, tzinfo=predict.KST)
    rows = predict.upcoming(records, now=now, horizon_days=45)
    assert len(rows) == 1
    assert rows[0]["kind"] == "confirmed"
    assert rows[0]["opens_at"] == "2026-10-20T06:00"


def test_alarm_time_is_ten_minutes_before():
    from courtfinder import predict

    assert predict.alarm_time("2026-10-20T06:00", 10).strftime("%H:%M") == "05:50"
    assert predict.alarm_time("2026-10-20T00:05", 10).strftime("%Y-%m-%d %H:%M") == "2026-10-19 23:55"


def test_alarm_message_flags_a_prediction():
    from courtfinder import predict

    entry = {"place": "신도림테니스장", "area": "구로구", "opens_at": "2026-10-25T07:00",
             "kind": "predicted", "use_start": "2026-11-01", "use_end": "2026-11-30"}
    text = predict.alarm_message(entry)
    assert "신도림테니스장" in text and "07:00" in text and "추정" in text
    assert "추정" not in predict.alarm_message(dict(entry, kind="confirmed"))


# ── ICS 구독 파일 ──────────────────────────────────────────────
def _ics_records():
    return [
        _rec("신도림테니스장", "2026-08-25T07:00", "2026-09-01", "2026-09-30", "A"),
        _rec("신도림테니스장", "2026-09-25T07:00", "2026-10-01", "2026-10-31", "B"),
        _rec("탄천물재생센터", "2026-09-25T14:00", "2026-01-01", "2026-12-31", "C"),
    ]


def _ics_now():
    import datetime as dtm

    from courtfinder import predict

    return dtm.datetime(2026, 9, 26, 12, 0, tzinfo=predict.KST)


def test_series_skips_standing_reservations():
    from courtfinder import ics

    events = ics.series(_ics_records(), now=_ics_now(), horizon_days=90)
    assert {e["place"] for e in events} == {"신도림테니스장"}


def test_series_generates_several_future_rounds():
    from courtfinder import ics

    events = ics.series(_ics_records(), now=_ics_now(), horizon_days=90)
    opens = [e["opens_at"].strftime("%Y-%m-%d %H:%M") for e in events]
    assert opens == ["2026-10-25 07:00", "2026-11-25 07:00", "2026-12-25 07:00"]
    assert all(e["kind"] == "predicted" for e in events)


def test_confirmed_posting_is_not_duplicated_by_a_prediction():
    from courtfinder import ics

    records = _ics_records() + [
        _rec("삼청테니스장", "2026-08-20T06:00", "2026-09-01", "2026-09-30", "D"),
        _rec("삼청테니스장", "2026-10-20T06:00", "2026-11-01", "2026-11-30", "E"),
    ]
    events = [e for e in ics.series(records, now=_ics_now(), horizon_days=60)
              if e["place"] == "삼청테니스장"]
    stamps = [e["opens_at"].strftime("%Y-%m-%d %H:%M") for e in events]
    assert stamps.count("2026-10-20 06:00") == 1
    assert events[0]["kind"] == "confirmed"


def test_render_is_wellformed_and_carries_alarms():
    from courtfinder import ics

    text = ics.render(_ics_records(), now=_ics_now(), horizon_days=90)
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert text.endswith("END:VCALENDAR\r\n")
    assert text.count("BEGIN:VEVENT") == text.count("END:VEVENT") == 3
    assert text.count("TRIGGER:-PT10M") == 3
    assert "X-WR-CALNAME:서울 테니스장 예약 오픈" in text
    # 개방 07:00 KST == 22:00Z 전날
    assert "DTSTART:20261024T220000Z" in text


def test_render_honours_a_custom_alarm_offset():
    from courtfinder import ics

    text = ics.render(_ics_records(), now=_ics_now(), minutes_before=30)
    assert "TRIGGER:-PT30M" in text
    assert "30분 뒤 열립니다" in text


def test_every_line_fits_the_ics_octet_limit():
    from courtfinder import ics

    text = ics.render(_ics_records(), now=_ics_now())
    assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))


def test_text_escaping_protects_separators():
    from courtfinder import ics

    assert ics._escape("a,b;c") == "a" + chr(92) + ",b" + chr(92) + ";c"
    assert ics._escape("줄1\n줄2") == "줄1\\n줄2"


def test_uid_is_stable_for_the_same_opening():
    import datetime as dtm

    from courtfinder import ics, predict

    when = dtm.datetime(2026, 10, 25, 7, 0, tzinfo=predict.KST)
    assert ics._uid("신도림", when) == ics._uid("신도림", when)
    assert ics._uid("신도림", when) != ics._uid("장충", when)

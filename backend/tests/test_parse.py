"""Unit tests for asuadvisr.scraper.parse using the pinned CSE Fall 2026 fixture."""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import pytest

from asuadvisr.scraper.parse import (
    _parse_date,
    _parse_time,
    parse_course,
    parse_meeting_times,
    parse_record,
    parse_section,
    parse_section_group,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cse_fall26_sample.json"


@pytest.fixture(scope="module")
def records() -> list[dict]:
    with FIXTURE.open() as f:
        data = json.load(f)
    return data["records"]  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def cse100_online(records: list[dict]) -> dict:
    """CSE 100 online LEC — no meeting time (STARTTIME=None)."""
    return next(r for r in records if r["CLAS"]["CLASSNBR"] == "62688")


@pytest.fixture(scope="module")
def cse100_inperson(records: list[dict]) -> dict:
    """CSE 100 in-person LEC — has STARTTIME and day flags."""
    return next(r for r in records if r["CLAS"]["CLASSNBR"] == "63697")


@pytest.fixture(scope="module")
def cse230_hybrid(records: list[dict]) -> dict:
    """CSE 230 hybrid section — STARTTIMES has a non-null + null entry."""
    return next(r for r in records if r["CLAS"]["CLASSNBR"] == "60357")


# ─── parse_date ───────────────────────────────────────────────────────────────


def test_parse_date_iso() -> None:
    assert _parse_date("2026-08-20 00:00:00.0") == date(2026, 8, 20)


def test_parse_date_slash() -> None:
    assert _parse_date("8/20/2026") == date(2026, 8, 20)


def test_parse_date_none() -> None:
    assert _parse_date(None) is None


def test_parse_date_empty() -> None:
    assert _parse_date("") is None


# ─── parse_time ───────────────────────────────────────────────────────────────


def test_parse_time_pm() -> None:
    assert _parse_time("12:20 PM") == time(12, 20)


def test_parse_time_am() -> None:
    assert _parse_time("9:00 AM") == time(9, 0)


def test_parse_time_midnight() -> None:
    assert _parse_time("12:00 AM") == time(0, 0)


def test_parse_time_noon() -> None:
    assert _parse_time("12:00 PM") == time(12, 0)


def test_parse_time_none() -> None:
    assert _parse_time(None) is None


# ─── parse_course ─────────────────────────────────────────────────────────────


def test_parse_course_fields(cse100_online: dict) -> None:
    clas = cse100_online["CLAS"]
    course = parse_course(clas)
    assert course["id"] == "104171"
    assert course["subject"] == "CSE"
    assert course["catalog_nbr"] == "100"
    assert course["units_min"] == 3.0
    assert course["units_max"] == 3.0
    assert isinstance(course["title"], str) and len(course["title"]) > 0


def test_parse_course_gs_designator(cse100_online: dict) -> None:
    course = parse_course(cse100_online["CLAS"])
    # CSE 100 has GS designation
    assert course["gs_designator"] == "GS02"


# ─── parse_section_group ──────────────────────────────────────────────────────


def test_parse_section_group(cse100_online: dict) -> None:
    clas = cse100_online["CLAS"]
    group = parse_section_group(clas)
    assert group["term_id"] == 2267
    assert group["course_id"] == "104171"
    assert group["assoc_class_label"] == "2101"
    assert group["ssr_count"] >= 1


# ─── parse_section ────────────────────────────────────────────────────────────


def test_parse_section_online(cse100_online: dict) -> None:
    clas = cse100_online["CLAS"]
    section = parse_section(clas, section_group_id=1)
    assert section["id"] == 62688
    assert section["component"] == "LEC"
    assert section["instruction_mode"] == "OL"
    assert section["enrl_cap"] == 225
    assert section["enrl_stat"] == "O"
    assert section["combined_id"] is None


def test_parse_section_inperson(cse100_inperson: dict) -> None:
    clas = cse100_inperson["CLAS"]
    section = parse_section(clas, section_group_id=2)
    assert section["id"] == 63697
    assert section["campus"] == "TEMPE"
    assert section["facility_id"] == "PSH152"


# ─── parse_meeting_times ──────────────────────────────────────────────────────


def test_meeting_times_online_empty(cse100_online: dict) -> None:
    """Online section with STARTTIME=None produces no meeting-time rows."""
    rows = parse_meeting_times(cse100_online["CLAS"], section_id=62688)
    assert rows == []


def test_meeting_times_inperson(cse100_inperson: dict) -> None:
    clas = cse100_inperson["CLAS"]
    rows = parse_meeting_times(clas, section_id=63697)
    assert len(rows) == 1
    r = rows[0]
    assert r["mon"] is True
    assert r["wed"] is True
    assert r["fri"] is True
    assert r["tue"] is False
    assert r["start_time"] == time(12, 20)
    assert r["end_time"] == time(13, 10)
    assert r["meeting_start_date"] == date(2026, 8, 20)


def test_meeting_times_hybrid_filters_null(cse230_hybrid: dict) -> None:
    """Hybrid section: only the non-null slot produces a row."""
    clas = cse230_hybrid["CLAS"]
    rows = parse_meeting_times(clas, section_id=60357)
    assert len(rows) == 1
    assert rows[0]["start_time"] == time(10, 30)
    assert rows[0]["end_time"] == time(11, 45)


# ─── parse_record (integration) ───────────────────────────────────────────────


def test_parse_record_shape(cse100_inperson: dict) -> None:
    parsed = parse_record(cse100_inperson)
    assert set(parsed.keys()) == {
        "course",
        "section_group",
        "section",
        "meeting_times",
        "instructors",
    }


def test_parse_record_instructor(cse100_inperson: dict) -> None:
    parsed = parse_record(cse100_inperson)
    assert len(parsed["instructors"]) == 1
    instr = parsed["instructors"][0]
    assert instr["last_name"] == "Kobayashi"
    assert instr["first_name"] == "Yoshihiro"
    assert instr["emplid"] == "ykobaya"


def test_parse_record_total_count(records: list[dict]) -> None:
    """All 283 records parse without raising."""
    for raw in records:
        parse_record(raw)  # should not raise

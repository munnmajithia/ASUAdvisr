"""Map raw ASU Class Search API records to DB-ready dicts.

Each public function returns a dict that matches the corresponding table's columns
exactly — no ORM, just plain dicts for Supabase upsert calls.

Field-mapping reference (from spike/FINDINGS.md):
  credits      → CLAS.UNITSMINIMUM / CLAS.UNITSMAXIMUM  (NOT the top-level HOURS)
  day flags    → CLAS.MON/TUES/WED/THURS/FRI/SAT/SUN as 'Y'/'N' strings
  lab+lecture  → CLAS.ASSOCIATEDCLASS (section label shared by coupled sections)
  cross-list   → CLAS.SCTNCOMBINEDID (empty string when not cross-listed)
  instructor   → INSTRUCTORSFIRSTNAMELIST / INSTRUCTORSLASTNAMELIST encoded as 'Name~emplid'
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import Any


def _yn(val: str | None) -> bool:
    return val == "Y"


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    # ASU dates: '2026-08-20 00:00:00.0' or 'M/D/YYYY'
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    return None


def _parse_time(raw: str | None) -> time | None:
    """Parse '12:20 PM' / '9:00 AM' → time object."""
    if not raw:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", raw.strip(), re.IGNORECASE)
    if not m:
        return None
    hour, minute, meridiem = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return time(hour, minute)


def _parse_instructors(rec: dict[str, Any]) -> list[dict[str, str]]:
    """Return list of {emplid, first_name, last_name} dicts from a raw record."""
    firsts: list[str] | None = rec.get("INSTRUCTORSFIRSTNAMELIST")
    lasts: list[str] | None = rec.get("INSTRUCTORSLASTNAMELIST")
    if not firsts or not lasts:
        return []
    result: list[dict[str, str]] = []
    for f_raw, l_raw in zip(firsts, lasts, strict=False):
        if not f_raw or "~" not in f_raw:
            continue
        first_name, emplid = f_raw.rsplit("~", 1)
        last_name = l_raw.rsplit("~", 1)[0] if l_raw and "~" in l_raw else ""
        result.append({"emplid": emplid, "first_name": first_name, "last_name": last_name})
    return result


# ─── Public parsers ───────────────────────────────────────────────────────────


def parse_course(clas: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": clas["CRSEID"],
        "subject": clas["SUBJECT"],
        "catalog_nbr": clas["CATALOGNBR"],
        "title": clas["COURSETITLELONG"],
        "units_min": float(clas["UNITSMINIMUM"]),
        "units_max": float(clas["UNITSMAXIMUM"]),
        "gs_designator": clas.get("RQMNTDESIGNTN") or None,
    }


def parse_section_group(clas: dict[str, Any]) -> dict[str, Any]:
    return {
        "term_id": int(clas["STRM"]),
        "course_id": clas["CRSEID"],
        "assoc_class_label": clas["ASSOCIATEDCLASS"],
        "ssr_count": int(clas.get("SSRCOUNT") or 1),
    }


def parse_section(clas: dict[str, Any], section_group_id: int) -> dict[str, Any]:
    combined = clas.get("SCTNCOMBINEDID") or None
    if combined == "":
        combined = None
    return {
        "id": int(clas["CLASSNBR"]),
        "section_group_id": section_group_id,
        "term_id": int(clas["STRM"]),
        "course_id": clas["CRSEID"],
        "section_label": clas["CLASSSECTION"],
        "component": clas["SSRCOMPONENT"],
        "instruction_mode": clas["INSTRUCTIONMODE"],
        "campus": clas["CAMPUS"],
        "location": clas.get("LOCATION") or None,
        "facility_id": clas.get("FACILITYID") or None,
        "enrl_cap": int(clas["ENRLCAP"]),
        "enrl_tot": int(clas["ENRLTOT"]),
        "enrl_stat": clas["ENRLSTAT"],
        "wait_cap": int(clas.get("WAITCAP") or 0),
        "wait_tot": int(clas.get("WAITTOT") or 0),
        "combined_id": combined,
        "session_code": clas.get("SESSIONCODE") or None,
        "start_date": (
            _parse_date(clas.get("STARTDATE")) or _parse_date(clas.get("OFFICIALSTARTDATE"))
        ),
        "end_date": (_parse_date(clas.get("ENDDATE")) or _parse_date(clas.get("OFFICIALENDDATE"))),
    }


def parse_meeting_times(clas: dict[str, Any], section_id: int) -> list[dict[str, Any]]:
    """Return one dict per non-null meeting slot in STARTTIMES."""
    start_times: list[Any] = clas.get("STARTTIMES") or [clas.get("STARTTIME")]
    end_times: list[Any] = clas.get("ENDTIMES") or [clas.get("ENDTIME")]
    meeting_dates: list[Any] = clas.get("MEETINGDATES") or []

    rows: list[dict[str, Any]] = []
    for i, (st, et) in enumerate(zip(start_times, end_times, strict=False)):
        if st is None:  # async / online slot — no time to store
            continue
        date_pair: list[str] | None = meeting_dates[i] if i < len(meeting_dates) else None
        rows.append(
            {
                "section_id": section_id,
                "mon": _yn(clas.get("MON")),
                "tue": _yn(clas.get("TUES")),
                "wed": _yn(clas.get("WED")),
                "thu": _yn(clas.get("THURS")),
                "fri": _yn(clas.get("FRI")),
                "sat": _yn(clas.get("SAT")),
                "sun": _yn(clas.get("SUN")),
                "start_time": _parse_time(st),
                "end_time": _parse_time(et),
                "meeting_start_date": _parse_date(date_pair[0]) if date_pair else None,
                "meeting_end_date": _parse_date(date_pair[1]) if date_pair else None,
            }
        )
    return rows


def parse_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse one top-level record from the API response into component dicts.

    Returns a dict with keys: course, section_group, section, meeting_times, instructors.
    section_group_id in 'section' is left as None — the caller must fill it in
    after upserting section_groups.
    """
    clas: dict[str, Any] = raw["CLAS"]
    # Instructor lists can live at the top level or inside CLAS depending on the response shape.
    first_list = raw.get("INSTRUCTORSFIRSTNAMELIST") or clas.get("INSTRUCTORSFIRSTNAMELIST")
    last_list = raw.get("INSTRUCTORSLASTNAMELIST") or clas.get("INSTRUCTORSLASTNAMELIST")
    merged = dict(clas)
    merged["INSTRUCTORSFIRSTNAMELIST"] = first_list
    merged["INSTRUCTORSLASTNAMELIST"] = last_list

    section_id = int(clas["CLASSNBR"])
    return {
        "course": parse_course(clas),
        "section_group": parse_section_group(clas),
        "section": parse_section(clas, section_group_id=0),  # caller patches group id
        "meeting_times": parse_meeting_times(clas, section_id=section_id),
        "instructors": _parse_instructors(merged),
    }

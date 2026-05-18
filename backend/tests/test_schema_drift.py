"""Daily smoke test asserting the ASU Class Search response shape hasn't drifted.

Loads the pinned fixture and asserts that the CLAS fields the parser depends on
are all present and non-empty for the CSE 100 section used as the canonical
reference (CLASSNBR 62688).
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "cse_fall26_sample.json"

# Fields that parse.py reads from CLAS — if any disappear the parser breaks.
REQUIRED_CLAS_FIELDS = {
    "CLASSNBR",
    "CLASSSECTION",
    "SSRCOMPONENT",
    "SSRCOUNT",
    "ASSOCIATEDCLASS",
    "SCTNCOMBINEDID",
    "STRM",
    "CRSEID",
    "SUBJECT",
    "CATALOGNBR",
    "COURSETITLELONG",
    "UNITSMINIMUM",
    "UNITSMAXIMUM",
    "RQMNTDESIGNTN",
    "INSTRUCTIONMODE",
    "CAMPUS",
    "LOCATION",
    "FACILITYID",
    "ENRLCAP",
    "ENRLTOT",
    "ENRLSTAT",
    "WAITCAP",
    "WAITTOT",
    "SESSIONCODE",
    "STARTDATE",
    "ENDDATE",
    "MON",
    "TUES",
    "WED",
    "THURS",
    "FRI",
    "SAT",
    "SUN",
    "STARTTIME",
    "ENDTIME",
    "STARTTIMES",
    "ENDTIMES",
    "MEETINGDATES",
    "INSTRUCTORSFIRSTNAMELIST",
    "INSTRUCTORSLASTNAMELIST",
}

REFERENCE_CLASS_NBR = "62688"  # CSE 100 section 2101, Fall 2026


def test_fixture_contains_reference_section() -> None:
    with FIXTURE.open() as f:
        data = json.load(f)

    records: list[dict] = data["records"]
    assert len(records) >= 200, f"expected ≥200 sections, got {len(records)}"

    match = next((r for r in records if r["CLAS"]["CLASSNBR"] == REFERENCE_CLASS_NBR), None)
    assert match is not None, f"reference section {REFERENCE_CLASS_NBR} not found in fixture"


def test_required_fields_present() -> None:
    with FIXTURE.open() as f:
        data = json.load(f)

    records: list[dict] = data["records"]
    match = next(r for r in records if r["CLAS"]["CLASSNBR"] == REFERENCE_CLASS_NBR)
    clas: dict = match["CLAS"]

    missing = REQUIRED_CLAS_FIELDS - set(clas.keys())
    assert not missing, f"CLAS fields missing from fixture: {missing}"


def test_reference_section_key_values() -> None:
    with FIXTURE.open() as f:
        data = json.load(f)

    records: list[dict] = data["records"]
    clas = next(r for r in records if r["CLAS"]["CLASSNBR"] == REFERENCE_CLASS_NBR)["CLAS"]

    assert clas["SUBJECT"] == "CSE"
    assert clas["CATALOGNBR"] == "100"
    assert clas["STRM"] == "2267"
    assert float(clas["UNITSMINIMUM"]) == 3.0
    assert float(clas["UNITSMAXIMUM"]) == 3.0

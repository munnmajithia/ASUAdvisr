"""FastAPI application — M2: POST /schedule + GET /courses."""

from __future__ import annotations

from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from asuadvisr.llm.constraint_parser import ParsedConstraints, parse_constraints
from asuadvisr.llm.dars_extractor import extract_profile
from asuadvisr.llm.requirement_profile import RequirementProfile
from asuadvisr.pdf.extract import PdfExtractionError, extract_text_from_bytes
from asuadvisr.scheduler.constraints import Day, ScheduleConstraints
from asuadvisr.scheduler.enumerate import (
    CourseRequirement,
    Schedule,
    SectionNode,
    enumerate_schedules,
    load_sections_from_fixture,
)

app = FastAPI(title="ASUAdvisr API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_FIXTURE = Path(__file__).parents[3] / "tests" / "fixtures" / "cse_fall26_sample.json"


@lru_cache(maxsize=1)
def _get_sections() -> dict[str, list[SectionNode]]:
    return load_sections_from_fixture(_FIXTURE)


# ─── Request / response models ────────────────────────────────────────────────


class RequirementIn(BaseModel):
    course_keys: list[str]
    pick: int = 1


class ConstraintsIn(BaseModel):
    avoid_days: list[Day] = []
    earliest_start: str | None = None  # "HH:MM" 24-hour
    latest_end: str | None = None
    min_credits: float | None = None
    max_credits: float | None = None
    preferred_modality: str | None = None
    only_open: bool = False

    def to_domain(self) -> ScheduleConstraints:
        def _t(s: str | None) -> time | None:
            if not s:
                return None
            h, m = s.split(":")
            return time(int(h), int(m))

        return ScheduleConstraints(
            avoid_days=list(self.avoid_days),
            earliest_start=_t(self.earliest_start),
            latest_end=_t(self.latest_end),
            min_credits=self.min_credits,
            max_credits=self.max_credits,
            preferred_modality=self.preferred_modality,
            only_open=self.only_open,
        )


class ScheduleRequest(BaseModel):
    requirements: list[RequirementIn]
    constraints: ConstraintsIn = ConstraintsIn()
    max_results: int = 50


class SectionDetail(BaseModel):
    id: int
    course_key: str
    component: str
    instruction_mode: str
    days: str  # e.g. "MWF"
    time_range: str  # e.g. "9:00 AM - 9:50 AM" or "Async"
    enrl_stat: str  # 'O' open, 'C' closed, 'W' waitlist, 'X'
    is_open: bool  # convenience flag: enrl_stat == 'O'


class ScheduleOut(BaseModel):
    sections: list[SectionDetail]
    total_credits: float


class ScheduleResponse(BaseModel):
    schedules: list[ScheduleOut]
    count: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _fmt_time(t: time) -> str:
    h = t.hour % 12 or 12
    ampm = "AM" if t.hour < 12 else "PM"
    return f"{h}:{t.minute:02d} {ampm}"


def _section_detail(node: SectionNode) -> SectionDetail:
    day_chars = [
        ("mon", "M"),
        ("tue", "T"),
        ("wed", "W"),
        ("thu", "Th"),
        ("fri", "F"),
        ("sat", "Sa"),
        ("sun", "Su"),
    ]
    if not node.meeting_slots:
        return SectionDetail(
            id=node.id,
            course_key=node.course_key,
            component=node.component,
            instruction_mode=node.instruction_mode,
            days="",
            time_range="Async",
            enrl_stat=node.enrl_stat,
            is_open=node.enrl_stat == "O",
        )
    slot = node.meeting_slots[0]
    days = "".join(abbr for attr, abbr in day_chars if getattr(slot, attr))
    if slot.start_time is None:
        time_range = "Async"
    elif slot.end_time is not None:
        time_range = f"{_fmt_time(slot.start_time)} - {_fmt_time(slot.end_time)}"
    else:
        time_range = _fmt_time(slot.start_time)
    return SectionDetail(
        id=node.id,
        course_key=node.course_key,
        component=node.component,
        instruction_mode=node.instruction_mode,
        days=days,
        time_range=time_range,
        enrl_stat=node.enrl_stat,
        is_open=node.enrl_stat == "O",
    )


def _build_output(schedule: Schedule, node_index: dict[int, SectionNode]) -> ScheduleOut:
    sections = [
        _section_detail(node_index[sid]) for sid in schedule.section_ids if sid in node_index
    ]
    return ScheduleOut(sections=sections, total_credits=schedule.total_credits)


class ParseConstraintsRequest(BaseModel):
    text: str


# ─── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse-constraints", response_model=ConstraintsIn)
def parse_constraints_endpoint(req: ParseConstraintsRequest) -> ConstraintsIn:
    try:
        parsed: ParsedConstraints = parse_constraints(req.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ConstraintsIn(**parsed.model_dump())


@app.get("/courses")
def list_courses() -> dict[str, list[str]]:
    """Sorted list of available course keys from the loaded data source."""
    return {"courses": sorted(_get_sections().keys())}


@app.post("/schedule", response_model=ScheduleResponse)
def schedule(req: ScheduleRequest) -> ScheduleResponse:
    sections_by_course = _get_sections()

    # Flat index for response enrichment.
    node_index: dict[int, SectionNode] = {
        node.id: node for nodes in sections_by_course.values() for node in nodes
    }

    requirements = [
        CourseRequirement(course_keys=r.course_keys, pick=r.pick) for r in req.requirements
    ]
    constraints = req.constraints.to_domain()
    results: list[Schedule] = enumerate_schedules(
        requirements=requirements,
        sections_by_course=sections_by_course,
        constraints=constraints,
        max_results=req.max_results,
    )
    return ScheduleResponse(
        schedules=[_build_output(s, node_index) for s in results],
        count=len(results),
    )


@app.post("/extract-requirements", response_model=RequirementProfile)
async def extract_requirements(file: Annotated[UploadFile, File()]) -> RequirementProfile:
    """Extract a draft RequirementProfile from an uploaded DARS / major-map PDF.

    Stateless: returns the parsed profile for the user to review and confirm. The
    confirmed profile is persisted client-side via Supabase (RLS-scoped), not here.
    """
    data = await file.read()
    try:
        text = extract_text_from_bytes(data)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        return extract_profile(text)
    except Exception as exc:  # LLM / upstream failure
        raise HTTPException(status_code=502, detail=str(exc)) from exc

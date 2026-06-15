"""Backtracking schedule enumerator for M2.

All logic is deterministic — no LLM involved.

Algorithm:
1. For each CourseRequirement, compute candidate picks. A pick is a list of
   SectionNodes that must be scheduled together (one per component type within
   one ASSOCIATEDCLASS group, e.g. LEC + LEL).
2. Sort requirements by fewest valid picks (most-constrained first).
3. Backtrack: try each pick for the current requirement; prune immediately when
   any section in the pick conflicts with already-scheduled slots.
4. Cap output at max_results; abandon after timeout_seconds and return partial.
"""

from __future__ import annotations

import json
import time as _time_mod
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Any

from asuadvisr.scheduler.constraints import (
    MeetingSlot,
    ScheduleConstraints,
    conflicts_with_any,
    section_passes_constraints,
)
from asuadvisr.scraper.parse import parse_record


@dataclass
class SectionNode:
    id: int
    course_key: str  # 'SUBJECT CATALOG_NBR', e.g. 'CSE 240'
    assoc_class_label: str  # ASSOCIATEDCLASS value used to group siblings
    ssr_count: int  # number of component types in the assoc group
    component: str  # 'LEC', 'LEL', 'PRA', etc.
    instruction_mode: str
    enrl_stat: str
    units: float
    meeting_slots: list[MeetingSlot] = field(default_factory=list)
    instructors: list[str] = field(default_factory=list)  # display names, e.g. 'Jane Doe'


@dataclass
class CourseRequirement:
    """One required course or a choice group (pick N of M courses)."""

    course_keys: list[str]  # 'SUBJECT CATALOG_NBR' identifiers
    pick: int = 1  # how many courses to select from course_keys


@dataclass
class Schedule:
    section_ids: list[int]
    total_credits: float


# ─── Assoc-group helpers ──────────────────────────────────────────────────────


def _iter_picks(
    sections: list[SectionNode],
    constraints: ScheduleConstraints,
) -> Iterator[list[SectionNode]]:
    """Yield every valid pick for one course.

    A pick is a list of sections that must be scheduled together (one per
    component type within one ASSOCIATEDCLASS group).
    """
    # Group by assoc_class_label, then by component within each group.
    by_label: dict[str, dict[str, list[SectionNode]]] = {}
    for s in sections:
        if constraints.only_open and s.enrl_stat != "O":
            continue  # skip closed/waitlisted sections
        by_label.setdefault(s.assoc_class_label, {}).setdefault(s.component, []).append(s)

    for component_map in by_label.values():
        buckets = list(component_map.values())
        for combo in product(*buckets):
            pick = list(combo)
            if all(section_passes_constraints(s.meeting_slots, constraints) for s in pick):
                yield pick


def _all_slots(sections: list[SectionNode]) -> list[MeetingSlot]:
    return [slot for s in sections for slot in s.meeting_slots]


# ─── Fixture loader ───────────────────────────────────────────────────────────


def load_sections_from_fixture(path: Path) -> dict[str, list[SectionNode]]:
    """Parse a raw API fixture into SectionNodes keyed by 'SUBJECT CATALOG_NBR'."""
    with path.open() as f:
        data: dict[str, Any] = json.load(f)

    by_course: dict[str, list[SectionNode]] = {}
    for raw in data["records"]:
        parsed = parse_record(raw)
        clas: dict[str, Any] = raw["CLAS"]
        course = parsed["course"]
        key = f"{course['subject']} {course['catalog_nbr']}"

        slots: list[MeetingSlot] = [
            MeetingSlot(
                mon=mt["mon"],
                tue=mt["tue"],
                wed=mt["wed"],
                thu=mt["thu"],
                fri=mt["fri"],
                sat=mt["sat"],
                sun=mt["sun"],
                start_time=mt["start_time"],
                end_time=mt["end_time"],
            )
            for mt in parsed["meeting_times"]
        ]

        instructors = [f"{i['first_name']} {i['last_name']}".strip() for i in parsed["instructors"]]

        node = SectionNode(
            id=parsed["section"]["id"],
            course_key=key,
            assoc_class_label=clas["ASSOCIATEDCLASS"],
            ssr_count=int(clas.get("SSRCOUNT") or 1),
            component=parsed["section"]["component"],
            instruction_mode=parsed["section"]["instruction_mode"],
            enrl_stat=parsed["section"]["enrl_stat"],
            units=float(clas["UNITSMINIMUM"]),
            meeting_slots=slots,
            instructors=instructors,
        )
        by_course.setdefault(key, []).append(node)

    return by_course


# ─── Core enumerator ─────────────────────────────────────────────────────────


def enumerate_schedules(
    requirements: list[CourseRequirement],
    sections_by_course: dict[str, list[SectionNode]],
    constraints: ScheduleConstraints,
    max_results: int = 50,
    timeout_seconds: float = 2.0,
) -> list[Schedule]:
    """Return up to max_results valid non-conflicting schedules."""
    results: list[Schedule] = []
    deadline = _time_mod.monotonic() + timeout_seconds

    # Build one list of candidate picks per requirement slot.
    # A choice group (pick=1 of N) merges all N courses' candidates together.
    candidate_lists: list[list[list[SectionNode]]] = []
    for req in requirements:
        picks: list[list[SectionNode]] = []
        for key in req.course_keys:
            secs = sections_by_course.get(key, [])
            picks.extend(_iter_picks(secs, constraints))
        if not picks:
            return []  # requirement is unsatisfiable
        candidate_lists.append(picks)

    # Most-constrained first (fewest valid picks).
    candidate_lists.sort(key=lambda cl: len(cl))

    def _backtrack(idx: int, chosen: list[list[SectionNode]]) -> None:
        if len(results) >= max_results or _time_mod.monotonic() > deadline:
            return
        if idx == len(candidate_lists):
            section_ids = [s.id for pick in chosen for s in pick]
            # Credits: count once per pick using the first section's units.
            total = sum(pick[0].units for pick in chosen)
            if constraints.min_credits is not None and total < constraints.min_credits:
                return
            if constraints.max_credits is not None and total > constraints.max_credits:
                return
            results.append(Schedule(section_ids=section_ids, total_credits=total))
            return

        scheduled_slots = [slot for pick in chosen for s in pick for slot in s.meeting_slots]
        for pick in candidate_lists[idx]:
            if not conflicts_with_any(_all_slots(pick), scheduled_slots):
                chosen.append(pick)
                _backtrack(idx + 1, chosen)
                chosen.pop()
                if len(results) >= max_results or _time_mod.monotonic() > deadline:
                    return

    _backtrack(0, [])
    return results

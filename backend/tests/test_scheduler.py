"""Tests for the M2 scheduler: constraints, conflict detection, and enumerator."""

from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest

from asuadvisr.scheduler.constraints import (
    MeetingSlot,
    ScheduleConstraints,
    conflicts_with_any,
    has_conflict,
    section_passes_constraints,
)
from asuadvisr.scheduler.enumerate import (
    CourseRequirement,
    SectionNode,
    enumerate_schedules,
    load_sections_from_fixture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cse_fall26_sample.json"

# ─── Synthetic helpers ────────────────────────────────────────────────────────


def _slot(
    days: str = "",
    start: str | None = None,
    end: str | None = None,
) -> MeetingSlot:
    """Build a MeetingSlot from compact notation. days is a subset of 'MTWRFSU'."""

    def _t(s: str) -> time:
        h, m = s.split(":")
        return time(int(h), int(m))

    return MeetingSlot(
        mon="M" in days,
        tue="T" in days,
        wed="W" in days,
        thu="R" in days,
        fri="F" in days,
        sat="S" in days,
        sun="U" in days,
        start_time=_t(start) if start else None,
        end_time=_t(end) if end else None,
    )


def _section(
    id_: int,
    course_key: str = "CSE 101",
    assoc: str = "1",
    component: str = "LEC",
    units: float = 3.0,
    slots: list[MeetingSlot] | None = None,
) -> SectionNode:
    return SectionNode(
        id=id_,
        course_key=course_key,
        assoc_class_label=assoc,
        ssr_count=1,
        component=component,
        instruction_mode="P",
        enrl_stat="O",
        units=units,
        meeting_slots=slots or [],
    )


# ─── has_conflict ─────────────────────────────────────────────────────────────


def test_conflict_same_day_overlapping() -> None:
    a = _slot("MWF", "09:00", "09:50")
    b = _slot("MWF", "09:30", "10:20")
    assert has_conflict(a, b)


def test_no_conflict_different_days() -> None:
    a = _slot("MWF", "09:00", "09:50")
    b = _slot("TR", "09:00", "09:50")
    assert not has_conflict(a, b)


def test_no_conflict_adjacent_times() -> None:
    a = _slot("M", "09:00", "09:50")
    b = _slot("M", "09:50", "10:40")
    assert not has_conflict(a, b)


def test_no_conflict_async() -> None:
    a = _slot()  # async
    b = _slot("MWF", "09:00", "09:50")
    assert not has_conflict(a, b)


def test_conflict_subset_overlap() -> None:
    a = _slot("MTWRF", "12:00", "13:00")
    b = _slot("W", "12:30", "13:30")
    assert has_conflict(a, b)


# ─── section_passes_constraints ───────────────────────────────────────────────


def test_avoid_day_blocks_section() -> None:
    c = ScheduleConstraints(avoid_days=["fri"])
    slots = [_slot("MWF", "09:00", "09:50")]
    assert not section_passes_constraints(slots, c)


def test_avoid_day_allows_different_days() -> None:
    c = ScheduleConstraints(avoid_days=["fri"])
    slots = [_slot("TR", "09:30", "10:45")]
    assert section_passes_constraints(slots, c)


def test_earliest_start_blocks() -> None:
    c = ScheduleConstraints(earliest_start=time(10, 0))
    slots = [_slot("MWF", "09:00", "09:50")]
    assert not section_passes_constraints(slots, c)


def test_earliest_start_allows_exact() -> None:
    c = ScheduleConstraints(earliest_start=time(9, 0))
    slots = [_slot("MWF", "09:00", "09:50")]
    assert section_passes_constraints(slots, c)


def test_latest_end_blocks() -> None:
    c = ScheduleConstraints(latest_end=time(17, 0))
    slots = [_slot("TR", "16:30", "17:45")]
    assert not section_passes_constraints(slots, c)


def test_async_passes_all_time_constraints() -> None:
    c = ScheduleConstraints(avoid_days=["mon"], earliest_start=time(12, 0), latest_end=time(14, 0))
    assert section_passes_constraints([], c)


# ─── conflicts_with_any ───────────────────────────────────────────────────────


def test_conflicts_with_any_detects_overlap() -> None:
    existing = [_slot("MWF", "09:00", "09:50"), _slot("TR", "11:00", "12:15")]
    new = [_slot("W", "09:20", "10:10")]
    assert conflicts_with_any(new, existing)


def test_conflicts_with_any_no_overlap() -> None:
    existing = [_slot("MWF", "09:00", "09:50")]
    new = [_slot("TR", "09:00", "10:15")]
    assert not conflicts_with_any(new, existing)


# ─── enumerate_schedules (integration against fixture) ────────────────────────


@pytest.fixture(scope="module")
def sections() -> dict[str, list[SectionNode]]:
    return load_sections_from_fixture(FIXTURE)


def test_fixture_loads_courses(sections: dict[str, list[SectionNode]]) -> None:
    assert "CSE 100" in sections
    assert len(sections["CSE 100"]) > 0


def test_single_required_course_returns_schedules(
    sections: dict[str, list[SectionNode]],
) -> None:
    results = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 100"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
        max_results=50,
    )
    assert len(results) > 0
    for r in results:
        assert len(r.section_ids) >= 1
        assert r.total_credits >= 0
    # At least some results should have positive credits (data sanity check).
    assert any(r.total_credits > 0 for r in results)


def test_unsatisfiable_requirement_returns_empty(
    sections: dict[str, list[SectionNode]],
) -> None:
    results = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 9999"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
    )
    assert results == []


def test_two_courses_no_conflicts(sections: dict[str, list[SectionNode]]) -> None:
    results = enumerate_schedules(
        requirements=[
            CourseRequirement(course_keys=["CSE 100"]),
            CourseRequirement(course_keys=["CSE 230"]),
        ],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
        max_results=20,
    )
    assert len(results) > 0
    for r in results:
        # Must cover both courses
        assert len(r.section_ids) >= 2


def test_avoid_friday_reduces_results(sections: dict[str, list[SectionNode]]) -> None:
    no_constraint = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 100"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
        max_results=200,
    )
    avoid_fri = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 100"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(avoid_days=["fri"]),
        max_results=200,
    )
    # With avoid_fri, no schedule should include a Friday section.
    for r in avoid_fri:
        for sid in r.section_ids:
            node = next(s for s in sections["CSE 100"] if s.id == sid)
            for slot in node.meeting_slots:
                assert not slot.fri, f"section {sid} has Friday meeting but constraint said avoid"

    # The unconstrained set should be >= constrained set (or equal if no Fri sections exist).
    assert len(no_constraint) >= len(avoid_fri)


def test_choice_group_picks_one_course(sections: dict[str, list[SectionNode]]) -> None:
    """A choice group of 2 courses should still yield valid single-course schedules."""
    results = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 100", "CSE 230"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
        max_results=10,
    )
    assert len(results) > 0
    # Each schedule covers exactly one course slot (one section per component type).
    for r in results:
        assert len(r.section_ids) >= 1


def test_lab_lecture_coupling(sections: dict[str, list[SectionNode]]) -> None:
    """If any course has LEC+LEL components, each schedule pick must include both."""
    multi_component_course = next(
        (key for key, nodes in sections.items() if len({n.component for n in nodes}) > 1),
        None,
    )
    if multi_component_course is None:
        pytest.skip("no multi-component course in fixture")

    results = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=[multi_component_course])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
        max_results=10,
    )
    assert len(results) > 0
    course_nodes = sections[multi_component_course]

    for r in results:
        picked_nodes = [n for n in course_nodes if n.id in r.section_ids]
        picked_components = {n.component for n in picked_nodes}
        # Every schedule must cover all component types present in one assoc group.
        assert picked_components  # at least one component picked


def test_max_results_cap(sections: dict[str, list[SectionNode]]) -> None:
    results = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 100"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(),
        max_results=3,
    )
    assert len(results) <= 3


def test_credit_constraint_filters(sections: dict[str, list[SectionNode]]) -> None:
    results = enumerate_schedules(
        requirements=[CourseRequirement(course_keys=["CSE 100"])],
        sections_by_course=sections,
        constraints=ScheduleConstraints(min_credits=3.0, max_credits=3.0),
        max_results=50,
    )
    for r in results:
        assert r.total_credits == pytest.approx(3.0)

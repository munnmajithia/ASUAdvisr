"""API-level tests.

These call the route handlers directly rather than via Starlette's TestClient.
TestClient spins up an anyio blocking portal that deadlocks under this repo's
``asyncio_mode = "auto"`` pytest config; the handlers are plain sync functions, so
calling them directly tests the same logic (request models in, response models out)
without that machinery. Async endpoints (e.g. file uploads) should use
``httpx.AsyncClient`` + ``ASGITransport`` inside an ``async def`` test instead.
"""

import pytest

from asuadvisr.api.main import (
    ConstraintsIn,
    RequirementIn,
    ScheduleRequest,
    list_courses,
    schedule,
)


def test_courses_endpoint() -> None:
    courses = list_courses()["courses"]
    assert isinstance(courses, list)
    assert courses, "fixture should expose at least one course"


def test_schedule_response_includes_seat_status() -> None:
    courses = list_courses()["courses"]
    for key in courses[:10]:
        resp = schedule(
            ScheduleRequest(requirements=[RequirementIn(course_keys=[key])], max_results=5)
        )
        if resp.schedules:
            section = resp.schedules[0].sections[0]
            assert section.enrl_stat  # populated, e.g. 'O'/'C'
            assert isinstance(section.is_open, bool)
            assert section.is_open == (section.enrl_stat == "O")
            assert isinstance(section.instructors, list)  # may be empty for some sections
            return
    pytest.skip("no schedulable course found in first 10 fixture courses")


def test_only_open_constraint_accepted() -> None:
    courses = list_courses()["courses"]
    resp = schedule(
        ScheduleRequest(
            requirements=[RequirementIn(course_keys=[courses[0]])],
            constraints=ConstraintsIn(only_open=True),
        )
    )
    assert isinstance(resp.schedules, list)


def test_unresolved_requirement_is_reported_not_silent() -> None:
    """A wildcard-only profile (no concrete options) must not silently yield []."""
    resp = schedule(ScheduleRequest(requirements=[RequirementIn(course_keys=[])]))
    assert resp.schedules == []
    assert resp.count == 0
    assert len(resp.dropped) == 1
    assert resp.dropped[0].reason == "unresolved"


def test_unknown_course_is_reported_as_no_candidates() -> None:
    resp = schedule(ScheduleRequest(requirements=[RequirementIn(course_keys=["ZZZ 999"])]))
    assert resp.schedules == []
    assert resp.count == 0
    assert len(resp.dropped) == 1
    assert resp.dropped[0].reason == "no_candidates"
    assert "ZZZ 999" in resp.dropped[0].detail


def test_dropped_requirement_does_not_block_others() -> None:
    """An unresolved requirement is excluded and reported; the rest still schedule."""
    courses = list_courses()["courses"]
    for key in courses[:10]:
        resp = schedule(
            ScheduleRequest(
                requirements=[RequirementIn(course_keys=[key]), RequirementIn(course_keys=[])],
                max_results=5,
            )
        )
        if resp.schedules:
            assert [d.reason for d in resp.dropped] == ["unresolved"]
            assert all(s.course_key == key for s in resp.schedules[0].sections)
            return
    pytest.skip("no schedulable course found in first 10 fixture courses")


def test_satisfiable_request_reports_no_dropped() -> None:
    courses = list_courses()["courses"]
    resp = schedule(ScheduleRequest(requirements=[RequirementIn(course_keys=[courses[0]])]))
    assert resp.dropped == []


def test_only_open_sections_are_open() -> None:
    """When only_open is set, every section in every returned schedule is open."""
    courses = list_courses()["courses"]
    for key in courses[:10]:
        resp = schedule(
            ScheduleRequest(
                requirements=[RequirementIn(course_keys=[key])],
                constraints=ConstraintsIn(only_open=True),
                max_results=10,
            )
        )
        if resp.schedules:
            for sched in resp.schedules:
                assert all(s.is_open for s in sched.sections)
            return
    pytest.skip("no open schedulable course found in first 10 fixture courses")

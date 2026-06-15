"""Soft-constraint ranking for enumerated schedules.

Fully deterministic — no LLM. Soft preferences *rank* valid schedules; they never
filter them (filtering is the job of the hard constraints in ``constraints.py``).
``schedule_score`` returns a penalty where **lower is better**, so callers sort
ascending. A schedule with no applicable soft preferences scores ``0.0``.
"""

from __future__ import annotations

from datetime import time
from itertools import pairwise

from asuadvisr.scheduler.constraints import MeetingSlot, ScheduleConstraints

_DAY_ATTRS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Each extra day on campus costs this many "minutes" in the compactness penalty,
# so a schedule packed into fewer days beats one with the same total gap spread out.
_DAY_WEIGHT = 120

_TIME_OF_DAY_WINDOWS: dict[str, tuple[time, time]] = {
    "morning": (time(8, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), time(22, 0)),
}


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _timed(slots: list[MeetingSlot]) -> list[MeetingSlot]:
    return [s for s in slots if s.start_time is not None]


def compactness_penalty(slots: list[MeetingSlot]) -> float:
    """Penalty combining days-on-campus and idle gap minutes between classes."""
    timed = _timed(slots)
    if not timed:
        return 0.0

    by_day: dict[str, list[MeetingSlot]] = {}
    for slot in timed:
        for day in _DAY_ATTRS:
            if getattr(slot, day):
                by_day.setdefault(day, []).append(slot)

    gap_minutes = 0
    for day_slots in by_day.values():
        ordered = sorted(day_slots, key=lambda s: _minutes(s.start_time))  # type: ignore[arg-type]
        for prev, nxt in pairwise(ordered):
            prev_end = prev.end_time or prev.start_time
            assert prev_end is not None and nxt.start_time is not None
            gap = _minutes(nxt.start_time) - _minutes(prev_end)
            if gap > 0:
                gap_minutes += gap

    return len(by_day) * _DAY_WEIGHT + gap_minutes


def time_of_day_penalty(slots: list[MeetingSlot], preference: str) -> float:
    """Penalty for each minute a class starts outside the preferred window."""
    window = _TIME_OF_DAY_WINDOWS.get(preference)
    if window is None:
        return 0.0
    lo, hi = _minutes(window[0]), _minutes(window[1])
    penalty = 0.0
    for slot in _timed(slots):
        assert slot.start_time is not None
        start = _minutes(slot.start_time)
        if start < lo:
            penalty += lo - start
        elif start > hi:
            penalty += start - hi
    return penalty


def schedule_score(slots: list[MeetingSlot], c: ScheduleConstraints) -> float:
    """Total soft-preference penalty for a schedule's meeting slots (lower is better)."""
    score = 0.0
    if c.compact_schedule:
        score += compactness_penalty(slots)
    if c.prefer_time_of_day:
        score += time_of_day_penalty(slots, c.prefer_time_of_day)
    return score

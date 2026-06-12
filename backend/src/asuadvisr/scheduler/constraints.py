"""Hard-constraint types and conflict/filter functions for the scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Literal

type Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class MeetingSlot:
    mon: bool = False
    tue: bool = False
    wed: bool = False
    thu: bool = False
    fri: bool = False
    sat: bool = False
    sun: bool = False
    start_time: time | None = None
    end_time: time | None = None


@dataclass
class ScheduleConstraints:
    avoid_days: list[Day] = field(default_factory=list)
    earliest_start: time | None = None
    latest_end: time | None = None
    min_credits: float | None = None
    max_credits: float | None = None
    preferred_modality: str | None = None  # 'P', 'OL', 'HY'


def has_conflict(a: MeetingSlot, b: MeetingSlot) -> bool:
    """True if slots a and b overlap on at least one shared day."""
    if a.start_time is None or b.start_time is None:
        return False  # async sections never conflict with anything
    if not any(getattr(a, d) and getattr(b, d) for d in _DAYS):
        return False
    a_end = a.end_time or a.start_time
    b_end = b.end_time or b.start_time
    return a.start_time < b_end and b.start_time < a_end


def _slot_ok(slot: MeetingSlot, c: ScheduleConstraints) -> bool:
    if slot.start_time is None:
        return True  # async — no time constraints apply
    for day in c.avoid_days:
        if getattr(slot, day):
            return False
    if c.earliest_start is not None and slot.start_time < c.earliest_start:
        return False
    return c.latest_end is None or slot.end_time is None or slot.end_time <= c.latest_end


def section_passes_constraints(slots: list[MeetingSlot], c: ScheduleConstraints) -> bool:
    """True if every meeting slot for a section satisfies the constraints."""
    return all(_slot_ok(s, c) for s in slots)


def conflicts_with_any(new_slots: list[MeetingSlot], existing: list[MeetingSlot]) -> bool:
    """True if any slot in new_slots conflicts with any slot in existing."""
    for a in new_slots:
        for b in existing:
            if has_conflict(a, b):
                return True
    return False

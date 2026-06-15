"""Tests for soft-constraint ranking (scheduler/rank.py)."""

from datetime import time

from asuadvisr.scheduler.constraints import MeetingSlot, ScheduleConstraints
from asuadvisr.scheduler.rank import (
    compactness_penalty,
    schedule_score,
    time_of_day_penalty,
)


def _slot(days: str, start: str, end: str) -> MeetingSlot:
    def _t(s: str) -> time:
        h, m = s.split(":")
        return time(int(h), int(m))

    return MeetingSlot(
        mon="M" in days,
        tue="T" in days,
        wed="W" in days,
        thu="R" in days,
        fri="F" in days,
        start_time=_t(start),
        end_time=_t(end),
    )


def test_no_soft_prefs_scores_zero() -> None:
    slots = [_slot("MWF", "09:00", "09:50")]
    assert schedule_score(slots, ScheduleConstraints()) == 0.0


def test_compact_fewer_days_is_better() -> None:
    one_day = [_slot("M", "09:00", "09:50"), _slot("M", "10:00", "10:50")]
    three_days = [
        _slot("M", "09:00", "09:50"),
        _slot("W", "10:00", "10:50"),
        _slot("F", "13:00", "13:50"),
    ]
    assert compactness_penalty(one_day) < compactness_penalty(three_days)


def test_compact_smaller_gaps_better() -> None:
    back_to_back = [_slot("M", "09:00", "09:50"), _slot("M", "10:00", "10:50")]
    big_gap = [_slot("M", "09:00", "09:50"), _slot("M", "15:00", "15:50")]
    assert compactness_penalty(back_to_back) < compactness_penalty(big_gap)


def test_time_of_day_within_window_no_penalty() -> None:
    morning = [_slot("MWF", "09:00", "09:50")]
    assert time_of_day_penalty(morning, "morning") == 0.0


def test_time_of_day_outside_window_penalised() -> None:
    afternoon = [_slot("MWF", "15:00", "15:50")]
    assert time_of_day_penalty(afternoon, "morning") > 0.0


def test_unknown_time_of_day_pref_is_zero() -> None:
    slots = [_slot("MWF", "15:00", "15:50")]
    assert time_of_day_penalty(slots, "whenever") == 0.0


def test_async_slots_ignored() -> None:
    async_only = [MeetingSlot()]  # no start_time
    assert compactness_penalty(async_only) == 0.0
    assert time_of_day_penalty(async_only, "morning") == 0.0


def test_score_combines_both_preferences() -> None:
    slots = [_slot("M", "15:00", "15:50"), _slot("W", "16:00", "16:50")]
    c = ScheduleConstraints(compact_schedule=True, prefer_time_of_day="morning")
    expected = compactness_penalty(slots) + time_of_day_penalty(slots, "morning")
    assert schedule_score(slots, c) == expected

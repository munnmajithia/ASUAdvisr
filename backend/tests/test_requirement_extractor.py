"""Tests for the deterministic PyMuPDF stage of M4 requirement extraction.

Runs against the committed, PII-free sanitized DARS fixture (see
``tests/fixtures/dars/README.md``). Regenerate the fixture with
``uv run python scripts/build_dars_fixture.py`` after editing the source audit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from asuadvisr.llm.requirement_extractor import (
    RequirementProfile,
    extract_requirements,
    extract_text,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "dars"
SANITIZED_PDF = FIXTURE_DIR / "dars_sanitized.pdf"
SANITIZED_TXT = FIXTURE_DIR / "dars_sanitized.txt"

# PII that must never survive into the committed fixture.
_PII = ["Munn", "Majithia", "1230356233", "ISEhIWludFNlcU5vPTE2OTAzNTcxMQ"]


@pytest.fixture(scope="module")
def text() -> str:
    return extract_text(SANITIZED_PDF)


def test_extracts_nonempty_audit(text: str) -> None:
    assert len(text) > 10_000
    assert "Full Requirements Degree Audit" in text
    assert "END OF ANALYSIS" in text


def test_matches_committed_text(text: str) -> None:
    # Regression lock: the .pdf and the human-readable .txt must stay in sync.
    # If PyMuPDF output changes, regenerate via scripts/build_dars_fixture.py.
    assert text == SANITIZED_TXT.read_text()


def test_accepts_bytes(text: str) -> None:
    # The upload path hands the extractor raw bytes, not a filesystem path.
    assert extract_text(SANITIZED_PDF.read_bytes()) == text


def test_fixture_is_pii_free(text: str) -> None:
    for needle in _PII:
        assert needle not in text


def test_captures_program_identity(text: str) -> None:
    assert "BS COMPUTER SCIENCE" in text
    assert "23-24 CATALOG" in text
    assert "Fall 2023" in text


@pytest.mark.parametrize("course", ["CSE 355", "CSE 365", "CSE 485", "CSE 486", "MAT 343"])
def test_unsatisfied_required_courses_present(text: str, course: str) -> None:
    # Each is an unmet single-course requirement (NEEDS ... / COURSE LIST: <course>).
    assert course in text


def test_choice_group_and_status_present(text: str) -> None:
    assert "CSE 412 OR CSE 434 OR CSE 445" in text  # an OR choice group
    assert "OPERATING SYSTEMS" in text  # CSE 330, currently in progress (NR)
    assert "AT LEAST ONE REQUIREMENT HAS NOT BEEN SATISFIED" in text


# ─── extract_requirements (LLM stage, mocked) ─────────────────────────────────


def _mock_client(tool_input: dict[str, Any]) -> MagicMock:
    """Mirror the live Claude response shape: one forced tool_use block."""
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.input = tool_input

    response = MagicMock()
    response.content = [tool_use]

    client = MagicMock()
    client.messages.create.return_value = response
    return client


_SAMPLE_INPUT: dict[str, Any] = {
    "catalog_year": "Fall 2023",
    "major": "Computer Science (BS)",
    "completed_courses": [
        {
            "course": "CSE 110",
            "title": "PRINCIPLES OF PROGRAMMING",
            "grade": "B",
            "term": "FA23",
            "credits": 3.0,
        },
        {"course": "CSE 330", "grade": "NR", "term": "SU26", "in_progress": True},
    ],
    "remaining_requirements": [
        {"label": "CSE 355", "options": ["CSE 355"], "pick": 1, "credits_needed": 3.0},
        {
            "label": "CSE 412 OR CSE 434 OR CSE 445",
            "options": ["CSE 412", "CSE 434", "CSE 445"],
            "pick": 1,
        },
        {
            "label": "CSE 4xx Electives",
            "options": [],
            "credits_needed": 12.0,
            "note": "any CSE 4xx, NOT FROM CSE 430",
        },
    ],
}


def test_extracts_program_identity() -> None:
    profile = extract_requirements("<audit text>", client=_mock_client(_SAMPLE_INPUT))
    assert profile.catalog_year == "Fall 2023"
    assert profile.major == "Computer Science (BS)"


def test_completed_courses_and_in_progress_flag() -> None:
    profile = extract_requirements("<audit text>", client=_mock_client(_SAMPLE_INPUT))
    assert {c.course for c in profile.completed_courses} == {"CSE 110", "CSE 330"}
    in_prog = next(c for c in profile.completed_courses if c.course == "CSE 330")
    assert in_prog.in_progress is True
    assert in_prog.grade == "NR"


def test_remaining_single_choice_and_wildcard() -> None:
    profile = extract_requirements("<audit text>", client=_mock_client(_SAMPLE_INPUT))
    reqs = {r.label: r for r in profile.remaining_requirements}
    # Single specific course → one option, pick 1.
    assert reqs["CSE 355"].options == ["CSE 355"]
    # OR choice group → all options, pick 1 (maps to scheduler CourseRequirement).
    choice = reqs["CSE 412 OR CSE 434 OR CSE 445"]
    assert choice.options == ["CSE 412", "CSE 434", "CSE 445"]
    assert choice.pick == 1
    # Open/wildcard elective → no concrete options, credits + note instead.
    wildcard = reqs["CSE 4xx Electives"]
    assert wildcard.options == []
    assert wildcard.credits_needed == 12.0
    assert wildcard.note is not None


def test_empty_profile_defaults() -> None:
    profile = extract_requirements("nothing useful", client=_mock_client({}))
    assert profile == RequirementProfile()


def test_audit_text_forwarded_to_api() -> None:
    client = _mock_client({})
    extract_requirements("FULL AUDIT TEXT HERE", client=client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["messages"][0]["content"] == "FULL AUDIT TEXT HERE"


def test_tool_choice_forced_and_model() -> None:
    client = _mock_client({})
    extract_requirements("whatever", client=client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract_requirements"}
    assert kwargs["model"] == "claude-opus-4-8"


def test_no_tool_use_block_raises() -> None:
    # A refusal can leave the response with no tool_use block despite forced
    # tool_choice — fail loudly, not with a bare StopIteration.
    text_block = MagicMock()
    text_block.type = "text"
    response = MagicMock()
    response.content = [text_block]
    response.stop_reason = "refusal"
    client = MagicMock()
    client.messages.create.return_value = response

    with pytest.raises(RuntimeError, match="no tool_use block"):
        extract_requirements("...", client=client)


def test_truncated_extraction_raises() -> None:
    response = MagicMock()
    response.stop_reason = "max_tokens"
    response.content = []
    client = MagicMock()
    client.messages.create.return_value = response

    with pytest.raises(RuntimeError, match="truncated"):
        extract_requirements("...", client=client)

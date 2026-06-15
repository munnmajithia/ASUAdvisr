"""Tests for the DARS requirement extractor.

Mocks the Anthropic client exactly like ``test_constraint_parser.py`` — no live API.
"""

from unittest.mock import MagicMock

from asuadvisr.llm.dars_extractor import extract_profile
from asuadvisr.llm.requirement_profile import RequirementProfile


def _mock_client(tool_input: dict) -> MagicMock:
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.input = tool_input

    response = MagicMock()
    response.content = [tool_use]

    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_extracts_completed_and_remaining() -> None:
    result = extract_profile(
        "audit text",
        client=_mock_client(
            {
                "catalog_year": "2024-2025",
                "major": "Computer Science",
                "completed_courses": ["CSE 110", "MAT 265"],
                "required_courses_remaining": ["CSE 310", "CSE 355"],
            }
        ),
    )
    assert result.catalog_year == "2024-2025"
    assert result.major == "Computer Science"
    assert result.completed_courses == ["CSE 110", "MAT 265"]
    assert result.required_courses_remaining == ["CSE 310", "CSE 355"]


def test_extracts_choice_group_with_choose_alias() -> None:
    result = extract_profile(
        "audit text",
        client=_mock_client(
            {
                "choice_groups": [
                    {"name": "CS Electives", "choose": 2, "course_keys": ["CSE 412", "CSE 420"]}
                ]
            }
        ),
    )
    assert len(result.choice_groups) == 1
    group = result.choice_groups[0]
    assert group.name == "CS Electives"
    assert group.pick == 2  # "choose" maps to pick
    assert group.course_keys == ["CSE 412", "CSE 420"]


def test_normalises_course_keys() -> None:
    result = extract_profile(
        "audit text",
        client=_mock_client({"required_courses_remaining": ["cse310", "mat 267"]}),
    )
    assert result.required_courses_remaining == ["CSE 310", "MAT 267"]


def test_empty_input_returns_default_profile() -> None:
    result = extract_profile("nothing useful", client=_mock_client({}))
    assert result == RequirementProfile()


def test_tool_choice_forced() -> None:
    client = _mock_client({})
    extract_profile("whatever", client=client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract_requirements"}


def test_dars_text_forwarded_to_api() -> None:
    client = _mock_client({})
    extract_profile("DARS audit body here", client=client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["messages"][0]["content"] == "DARS audit body here"

"""Tests for the natural-language → ScheduleConstraints parser."""

from unittest.mock import MagicMock

from asuadvisr.llm.constraint_parser import ParsedConstraints, parse_constraints


def _mock_client(tool_input: dict) -> MagicMock:
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.input = tool_input

    response = MagicMock()
    response.content = [tool_use]

    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_avoid_single_day() -> None:
    result = parse_constraints("no Friday classes", client=_mock_client({"avoid_days": ["fri"]}))
    assert result.avoid_days == ["fri"]


def test_avoid_multiple_days() -> None:
    result = parse_constraints(
        "no Monday or Wednesday",
        client=_mock_client({"avoid_days": ["mon", "wed"]}),
    )
    assert result.avoid_days == ["mon", "wed"]


def test_earliest_start() -> None:
    result = parse_constraints(
        "nothing before 10am", client=_mock_client({"earliest_start": "10:00"})
    )
    assert result.earliest_start == "10:00"


def test_latest_end() -> None:
    result = parse_constraints(
        "done by 5pm", client=_mock_client({"latest_end": "17:00"})
    )
    assert result.latest_end == "17:00"


def test_credit_range() -> None:
    result = parse_constraints(
        "12 to 15 credits",
        client=_mock_client({"min_credits": 12.0, "max_credits": 15.0}),
    )
    assert result.min_credits == 12.0
    assert result.max_credits == 15.0


def test_modality_online() -> None:
    result = parse_constraints(
        "online only", client=_mock_client({"preferred_modality": "OL"})
    )
    assert result.preferred_modality == "OL"


def test_modality_in_person() -> None:
    result = parse_constraints(
        "I want in-person classes", client=_mock_client({"preferred_modality": "P"})
    )
    assert result.preferred_modality == "P"


def test_combined() -> None:
    result = parse_constraints(
        "no Friday, nothing before 10am, 12-15 credits",
        client=_mock_client({
            "avoid_days": ["fri"],
            "earliest_start": "10:00",
            "min_credits": 12.0,
            "max_credits": 15.0,
        }),
    )
    assert result.avoid_days == ["fri"]
    assert result.earliest_start == "10:00"
    assert result.min_credits == 12.0
    assert result.max_credits == 15.0
    assert result.latest_end is None
    assert result.preferred_modality is None


def test_empty_input_returns_defaults() -> None:
    result = parse_constraints("I don't care", client=_mock_client({}))
    assert result == ParsedConstraints()


def test_user_text_forwarded_to_api() -> None:
    client = _mock_client({})
    parse_constraints("no Mondays please", client=client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["messages"][0]["content"] == "no Mondays please"


def test_tool_choice_forced() -> None:
    client = _mock_client({})
    parse_constraints("whatever", client=client)
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract_constraints"}

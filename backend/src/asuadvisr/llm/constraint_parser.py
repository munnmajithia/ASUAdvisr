"""Natural language → ScheduleConstraints parser using Claude tool_use."""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel

from asuadvisr.scheduler.constraints import Day
from asuadvisr.settings import get_settings

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are a scheduling assistant for ASU students. "
    "Extract hard scheduling constraints from the student's message. "
    "Only extract constraints that are explicitly stated — do not infer or assume. "
    "Convert times to 24-hour HH:MM format (e.g. '10am' → '10:00', '2:30pm' → '14:30')."
)

_TOOL: dict[str, Any] = {
    "name": "extract_constraints",
    "description": "Extract scheduling hard constraints from a student's natural language request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "avoid_days": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                },
                "description": "Days the student wants no classes.",
            },
            "earliest_start": {
                "type": "string",
                "description": "Earliest acceptable start time, HH:MM 24-hour format.",
            },
            "latest_end": {
                "type": "string",
                "description": "Latest acceptable end time, HH:MM 24-hour format.",
            },
            "min_credits": {
                "type": "number",
                "description": "Minimum total credit hours for the schedule.",
            },
            "max_credits": {
                "type": "number",
                "description": "Maximum total credit hours for the schedule.",
            },
            "preferred_modality": {
                "type": "string",
                "enum": ["P", "OL", "HY"],
                "description": "P = in-person, OL = online, HY = hybrid.",
            },
        },
        "required": [],
    },
    # Cache the tool definition — it never changes between requests.
    "cache_control": {"type": "ephemeral"},
}


class ParsedConstraints(BaseModel):
    avoid_days: list[Day] = []
    earliest_start: str | None = None  # "HH:MM" 24-hour
    latest_end: str | None = None
    min_credits: float | None = None
    max_credits: float | None = None
    preferred_modality: str | None = None  # "P", "OL", or "HY"


def parse_constraints(
    text: str,
    client: anthropic.Anthropic | None = None,
) -> ParsedConstraints:
    """Parse natural language scheduling preferences into hard constraints."""
    if client is None:
        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    response = client.messages.create(  # type: ignore[call-overload]
        model=_MODEL,
        max_tokens=512,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "extract_constraints"},
        messages=[{"role": "user", "content": text}],
    )

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return ParsedConstraints.model_validate(tool_use_block.input)

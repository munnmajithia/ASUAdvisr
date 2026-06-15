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
    "Extract scheduling constraints and preferences from the student's message. "
    "Hard constraints (days, times, credits, modality) filter schedules; soft "
    "preferences (compact schedule, time of day) only rank them. "
    "Only extract what is explicitly stated — do not infer or assume. "
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
            "compact_schedule": {
                "type": "boolean",
                "description": "True if the student wants a compact schedule — classes close "
                "together, fewer days on campus, minimal gaps. Soft preference (ranks only).",
            },
            "prefer_time_of_day": {
                "type": "string",
                "enum": ["morning", "afternoon", "evening"],
                "description": "Preferred time of day for classes. Soft preference (ranks only).",
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
    compact_schedule: bool = False  # soft: prefer fewer days / smaller gaps
    prefer_time_of_day: str | None = None  # soft: "morning", "afternoon", "evening"


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

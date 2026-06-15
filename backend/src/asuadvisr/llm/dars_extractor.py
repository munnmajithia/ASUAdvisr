"""DARS / major-map text → RequirementProfile using Claude tool_use.

Mirrors ``constraint_parser.py``: forced tool choice, prompt caching on the
system prompt and tool definition, and Pydantic validation of the tool input.
"""

from __future__ import annotations

from typing import Any

import anthropic

from asuadvisr.llm.requirement_profile import RequirementProfile
from asuadvisr.settings import get_settings

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You parse academic records for ASU students. "
    "From a DARS degree-audit or major-map text, extract the student's degree "
    "requirements: the catalog year, major, courses already completed, the specific "
    "required courses still remaining, and any 'choose N from' requirement groups. "
    "Emit every course code as 'SUBJECT CATALOG_NBR' (e.g. 'CSE 240'). "
    "Only extract what is explicitly present — do not infer or invent requirements."
)

_TOOL: dict[str, Any] = {
    "name": "extract_requirements",
    "description": "Extract a student's degree-requirement profile from DARS / major-map text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "catalog_year": {
                "type": "string",
                "description": "Catalog / requirement year, e.g. '2024-2025'.",
            },
            "major": {"type": "string", "description": "Major or program name."},
            "completed_courses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Courses the student has completed, each as 'SUBJECT NUMBER'.",
            },
            "required_courses_remaining": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific required courses not yet completed, each as 'SUBJECT NUMBER'.",
            },
            "choice_groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Group label, e.g. 'CS Electives' or 'General Studies HUAD'.",
                        },
                        "choose": {
                            "type": "integer",
                            "description": "How many courses must be picked from this group.",
                        },
                        "course_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Candidate courses for the group, each as 'SUBJECT NUMBER'.",
                        },
                        "filter": {
                            "type": "string",
                            "description": "Textual rule when explicit courses are not listed (e.g. 'gen studies: HUAD').",
                        },
                    },
                    "required": ["name"],
                },
                "description": "'Choose N from M' requirement groups (electives, gen-studies buckets).",
            },
        },
        "required": [],
    },
    # The tool definition never changes between requests — cache it.
    "cache_control": {"type": "ephemeral"},
}


def extract_profile(
    text: str,
    client: anthropic.Anthropic | None = None,
) -> RequirementProfile:
    """Extract a :class:`RequirementProfile` from DARS / major-map text."""
    if client is None:
        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    response = client.messages.create(  # type: ignore[call-overload]
        model=_MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "extract_requirements"},
        messages=[{"role": "user", "content": text}],
    )

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return RequirementProfile.model_validate(tool_use_block.input)

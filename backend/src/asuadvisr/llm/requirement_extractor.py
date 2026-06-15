"""DARS / degree-audit PDF → RequirementProfile.

M4 requirement extraction runs in two stages:

1. Deterministic text extraction (`extract_text`) — PyMuPDF reads the uploaded
   audit PDF into linear, reading-order text. No interpretation happens here.
2. LLM extraction (`extract_requirements`) — Claude maps that text to a
   ``RequirementProfile`` (catalog year, major, completed courses, remaining
   requirements). Its output is **draft data, never trusted silently**: the
   onboarding flow shows it in an editable review UI before it feeds the
   scheduler. Expect ~60-70% raw accuracy across colleges; the review UI closes
   the gap.

`extract_profile` chains both stages (PDF → profile). The module is developed
against the sanitized fixture in ``backend/tests/fixtures/dars/`` (see its
README); the real audit PDF is gitignored because it contains student PII.

The remaining-requirement shape mirrors the scheduler's ``CourseRequirement``
(``asuadvisr.scheduler.enumerate``): ``options`` → ``course_keys``, ``pick`` →
``pick``. A single-course requirement is one option; a choice group is several.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anthropic
import fitz  # PyMuPDF
from pydantic import BaseModel, Field

from asuadvisr.settings import get_settings

_MODEL = "claude-opus-4-8"


# ─── Output schema ──────────────────────────────────────────────────────────


class CompletedCourse(BaseModel):
    """A course the student has taken or is currently taking."""

    course: str = Field(description="Course code as 'SUBJECT NUMBER', e.g. 'CSE 110'.")
    title: str | None = Field(default=None, description="Course title if shown.")
    grade: str | None = Field(
        default=None,
        description="Grade as printed (e.g. 'A', 'B-', 'AP'); 'NR' if in progress.",
    )
    term: str | None = Field(default=None, description="Term code if shown, e.g. 'FA23'.")
    credits: float | None = Field(default=None, description="Credit hours if shown.")
    in_progress: bool = Field(
        default=False,
        description="True if the course is in progress (grade 'NR' or an IN-PROGRESS section).",
    )


class RemainingRequirement(BaseModel):
    """An unmet requirement: take `pick` course(s) from `options`.

    Maps onto the scheduler's CourseRequirement(course_keys=options, pick=pick).
    """

    label: str = Field(
        description="Human-readable requirement, e.g. 'CSE 355' or 'CSE 412 OR CSE 434 OR CSE 445'.",
    )
    options: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete course codes ('SUBJECT NUMBER') that satisfy this requirement. "
            "One entry for a specific course; several for an OR choice. Leave empty for "
            "open electives or wildcards (e.g. 'any CSE 4xx') and describe them in `note`."
        ),
    )
    pick: int = Field(default=1, description="How many of `options` the student must take.")
    credits_needed: float | None = Field(
        default=None, description="Credit hours still needed, when the audit states an hour count."
    )
    note: str | None = Field(
        default=None,
        description="Caveats: wildcard patterns ('any CSE 4xx'), 'NOT FROM' exclusions, etc.",
    )


class RequirementProfile(BaseModel):
    """What a student still needs to graduate, extracted from a degree audit."""

    catalog_year: str | None = Field(
        default=None, description="Catalog year, e.g. '2023-2024' or 'Fall 2023'."
    )
    major: str | None = Field(
        default=None, description="Degree program, e.g. 'Computer Science (BS)'."
    )
    completed_courses: list[CompletedCourse] = Field(default_factory=list)
    remaining_requirements: list[RemainingRequirement] = Field(default_factory=list)


# ─── Prompt + tool ────────────────────────────────────────────────────────────

_SYSTEM = (
    "You extract a structured degree-completion profile from the text of an ASU "
    "uAchieve / DARS degree audit. Extract only what the audit states — never infer "
    "or invent courses or requirements.\n\n"
    "Audit conventions:\n"
    "- A course appears as a run of lines: TERM (e.g. SU26) / a one-letter source flag "
    "then SUBJECT NUMBER (e.g. 'M CSE 301') / hours / grade / optional flag ('>R' repeat, "
    "'>>' in progress) / title. Grade 'NR' and 'IN PROGRESS'/'IP' sections mean in progress; "
    "'AP' is test credit; a '*' or 'E'/'EU' grade is a failed or removed attempt.\n"
    "- A requirement names itself ('CSE 355: 3 hours, C minimum', 'Upper Division Technical "
    "Electives: 6 hours') then shows status: 'NEEDS:' (unmet), 'X.00 Hours Earned'/'EARNED:' "
    "(satisfied), or 'IN-PROG>' (covered by in-progress work). 'COURSE LIST:' / 'OR' lines "
    "give the courses that satisfy it; '-> NOT FROM:' lists exclusions.\n\n"
    "Rules:\n"
    "- Normalize every course code to uppercase 'SUBJECT NUMBER' (e.g. 'CSE 110', 'MAT 267').\n"
    "- completed_courses: every DISTINCT course taken or in progress. If a course was repeated, "
    "include it once using the best/most-recent attempt; set in_progress when its current "
    "attempt is in progress and it has not yet been passed.\n"
    "- remaining_requirements: only requirements still UNMET (a 'NEEDS:' status not fully covered). "
    "A specific course → options is that one course, pick 1. An 'A OR B OR C' choice → all options, "
    "pick 1. A wildcard/open elective ('CSE 4** Electives', technical electives) → leave options "
    "empty, set credits_needed, and put the wildcard pattern and any NOT-FROM exclusions in note.\n"
    "- Do NOT list satisfied requirements, and do NOT put in-progress courses in "
    "remaining_requirements (they belong in completed_courses with in_progress=true)."
)

_TOOL: dict[str, Any] = {
    "name": "extract_requirements",
    "description": "Record the degree-completion profile extracted from a degree audit.",
    "input_schema": RequirementProfile.model_json_schema(),
    # The tool schema never changes between requests — cache it.
    "cache_control": {"type": "ephemeral"},
}


# ─── Stage 1: deterministic text extraction ─────────────────────────────────


def extract_text(source: str | Path | bytes) -> str:
    """Extract the full text of a degree-audit PDF in reading order.

    Accepts a filesystem path or the raw PDF bytes (as uploaded by the student).
    Pages are concatenated in order; PyMuPDF newline-terminates each page's text,
    so the result preserves the audit's top-to-bottom line structure that the
    downstream LLM stage relies on.
    """
    if isinstance(source, bytes | bytearray):
        doc = fitz.open(stream=bytes(source), filetype="pdf")
    else:
        doc = fitz.open(source)
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


# ─── Stage 2: LLM extraction ─────────────────────────────────────────────────


def extract_requirements(
    text: str,
    client: anthropic.Anthropic | None = None,
) -> RequirementProfile:
    """Extract a RequirementProfile from degree-audit text via Claude.

    The result is draft data for the review UI, not ground truth.
    """
    if client is None:
        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    response = client.messages.create(  # type: ignore[call-overload]
        model=_MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "extract_requirements"},
        messages=[{"role": "user", "content": text}],
    )

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return RequirementProfile.model_validate(tool_use_block.input)


def extract_profile(
    source: str | Path | bytes,
    client: anthropic.Anthropic | None = None,
) -> RequirementProfile:
    """Convenience: degree-audit PDF → RequirementProfile (both stages)."""
    return extract_requirements(extract_text(source), client=client)

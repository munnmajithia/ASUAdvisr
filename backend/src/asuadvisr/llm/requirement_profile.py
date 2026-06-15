"""Shared RequirementProfile contract.

This is the single source of truth for the parsed-DARS shape: the LLM extractor
returns it, the extraction endpoint serialises it, and the SQL tables mirror its
fields. Style mirrors ``ParsedConstraints`` in ``constraint_parser.py``.

The deterministic scheduler consumes ``CourseRequirement`` objects, so this module
also owns the canonical profile → scheduler-input mapping (``to_requirements``).
The frontend re-implements the same mapping in TypeScript for the live flow; this
Python copy documents the contract and is unit-tested.
"""

from __future__ import annotations

import re

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from asuadvisr.scheduler.enumerate import CourseRequirement

# Matches a course code with optional space, e.g. "CSE 240", "cse240", "MAT  267".
_COURSE_KEY_RE = re.compile(r"^\s*([A-Za-z]{2,4})\s*(\d{1,4}[A-Za-z]?)\s*$")


def normalize_course_key(raw: str) -> str:
    """Normalise a course code to ``"SUBJECT CATALOG_NBR"`` (e.g. ``"cse240"`` → ``"CSE 240"``).

    Leaves anything that doesn't look like a course code untouched apart from
    trimming and upper-casing. Leading zeros in the number are preserved.
    """
    match = _COURSE_KEY_RE.match(raw)
    if match is None:
        return raw.strip().upper()
    subject, number = match.groups()
    return f"{subject.upper()} {number.upper()}"


class ChoiceGroup(BaseModel):
    """A "pick N of M" requirement set (e.g. a gen-studies bucket or elective pool)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = ""
    # Accept either "pick" or "choose" from the LLM tool output.
    pick: int = Field(default=1, validation_alias=AliasChoices("pick", "choose"))
    course_keys: list[str] = []
    filter: str | None = None  # textual fallback when no explicit keys are known

    @field_validator("course_keys", mode="after")
    @classmethod
    def _normalize_keys(cls, value: list[str]) -> list[str]:
        return [normalize_course_key(key) for key in value]


class RequirementProfile(BaseModel):
    """A student's degree-progress profile extracted from a DARS / major map."""

    catalog_year: str | None = None
    major: str | None = None
    completed_courses: list[str] = []
    required_courses_remaining: list[str] = []
    choice_groups: list[ChoiceGroup] = []

    @field_validator("completed_courses", "required_courses_remaining", mode="after")
    @classmethod
    def _normalize_keys(cls, value: list[str]) -> list[str]:
        return [normalize_course_key(key) for key in value]

    def to_requirements(self) -> list[CourseRequirement]:
        """Map the profile to scheduler input.

        Each remaining required course → one ``CourseRequirement`` (pick 1). Each
        choice group with explicit course keys → one ``CourseRequirement(pick=N)``.
        Completed courses are excluded; choice groups with only a textual ``filter``
        and no keys are skipped (nothing concrete to schedule yet).
        """
        requirements = [
            CourseRequirement(course_keys=[course], pick=1)
            for course in self.required_courses_remaining
        ]
        requirements.extend(
            CourseRequirement(course_keys=group.course_keys, pick=group.pick)
            for group in self.choice_groups
            if group.course_keys
        )
        return requirements

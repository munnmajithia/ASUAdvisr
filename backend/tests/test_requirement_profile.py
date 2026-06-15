"""Tests for the shared RequirementProfile contract and its scheduler mapping."""

from asuadvisr.llm.requirement_profile import (
    ChoiceGroup,
    RequirementProfile,
    normalize_course_key,
)


def test_profile_defaults_empty() -> None:
    profile = RequirementProfile()
    assert profile.catalog_year is None
    assert profile.major is None
    assert profile.completed_courses == []
    assert profile.required_courses_remaining == []
    assert profile.choice_groups == []
    assert profile.to_requirements() == []


def test_validate_from_dict_round_trips() -> None:
    profile = RequirementProfile.model_validate(
        {
            "catalog_year": "2024-2025",
            "major": "Computer Science",
            "completed_courses": ["CSE 110"],
            "required_courses_remaining": ["CSE 310", "CSE 355"],
            "choice_groups": [{"name": "CS Electives", "pick": 1, "course_keys": ["CSE 412"]}],
        }
    )
    assert profile.major == "Computer Science"
    assert profile.required_courses_remaining == ["CSE 310", "CSE 355"]
    assert profile.choice_groups[0].name == "CS Electives"


def test_choice_group_choose_alias() -> None:
    assert ChoiceGroup.model_validate({"choose": 2}).pick == 2
    assert ChoiceGroup.model_validate({"pick": 2}).pick == 2
    assert ChoiceGroup.model_validate({}).pick == 1


def test_to_requirements_required() -> None:
    profile = RequirementProfile(required_courses_remaining=["CSE 310", "CSE 355", "MAT 267"])
    reqs = profile.to_requirements()
    assert len(reqs) == 3
    assert all(len(r.course_keys) == 1 and r.pick == 1 for r in reqs)
    assert [r.course_keys[0] for r in reqs] == ["CSE 310", "CSE 355", "MAT 267"]


def test_to_requirements_choice_group() -> None:
    profile = RequirementProfile(
        choice_groups=[
            ChoiceGroup(name="Electives", pick=2, course_keys=["CSE 412", "CSE 420", "CSE 445"])
        ]
    )
    reqs = profile.to_requirements()
    assert len(reqs) == 1
    assert reqs[0].pick == 2
    assert reqs[0].course_keys == ["CSE 412", "CSE 420", "CSE 445"]


def test_to_requirements_excludes_completed_and_keyless_groups() -> None:
    profile = RequirementProfile(
        completed_courses=["CSE 110"],
        required_courses_remaining=["CSE 310"],
        choice_groups=[ChoiceGroup(name="HUAD", pick=1, filter="gen_studies:HUAD")],
    )
    reqs = profile.to_requirements()
    # Only the one remaining required course; completed and keyless group excluded.
    assert len(reqs) == 1
    assert reqs[0].course_keys == ["CSE 310"]


def test_course_key_normalisation() -> None:
    assert normalize_course_key("cse240") == "CSE 240"
    assert normalize_course_key("CSE  240") == "CSE 240"
    assert normalize_course_key(" mat267 ") == "MAT 267"
    assert normalize_course_key("CSE 110") == "CSE 110"  # leading-zero-free, unchanged
    # Fields normalise on validation.
    profile = RequirementProfile(required_courses_remaining=["cse310", "mat 267"])
    assert profile.required_courses_remaining == ["CSE 310", "MAT 267"]
    group = ChoiceGroup(course_keys=["cse412", "CSE420"])
    assert group.course_keys == ["CSE 412", "CSE 420"]

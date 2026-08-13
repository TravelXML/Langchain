from __future__ import annotations

import pytest

from app.browser.mapping import map_field, map_fields
from app.browser.models import DetectedField
from app.profile.models import ExtractedField
from tests.fixtures.job_builder import make_preferences, make_profile, make_resume


def _field(label: str, **overrides) -> DetectedField:
    defaults = dict(name="f", label=label, field_type="text", selector="#f")
    defaults.update(overrides)
    return DetectedField(**defaults)


def test_maps_email_field():
    mapping = map_field(_field("Email"), make_profile())
    assert mapping.candidate_value == "jordan@example.com"
    assert mapping.requires_human is False
    assert mapping.source == "profile"


def test_maps_experience_years_field():
    mapping = map_field(_field("Years of Experience"), make_profile())
    assert mapping.candidate_value == "15"
    assert mapping.requires_human is False


def test_maps_current_title_field():
    profile = make_profile(
        resume=make_resume(
            current_title=ExtractedField[str](
                value="VP Engineering", source="resume", confidence=0.8
            )
        )
    )
    mapping = map_field(_field("Current Title"), profile)
    assert mapping.candidate_value == "VP Engineering"
    assert mapping.requires_human is False


def test_maps_work_mode_field():
    profile = make_profile(preferences=make_preferences(work_mode=["remote", "hybrid"]))
    mapping = map_field(_field("Preferred Work Mode"), profile)
    assert mapping.candidate_value == "remote"
    assert mapping.requires_human is False


def test_maps_work_authorization_when_stated():
    profile = make_profile(preferences=make_preferences(work_authorization="citizen"))
    mapping = map_field(_field("Work Authorization"), profile)
    assert mapping.candidate_value == "citizen"
    assert mapping.requires_human is False


def test_work_authorization_requires_human_when_unstated():
    profile = make_profile(preferences=make_preferences(work_authorization=None))
    mapping = map_field(_field("Are you authorized to work in this country?"), profile)
    assert mapping.candidate_value is None
    assert mapping.requires_human is True


@pytest.mark.parametrize(
    "label",
    [
        "Gender",
        "Ethnicity",
        "Do you have a disability?",
        "Veteran Status",
        "Religion",
        "Security Clearance",
        "Criminal History",
    ],
)
def test_sensitive_fields_always_require_human(label: str):
    mapping = map_field(_field(label), make_profile())
    assert mapping.candidate_value is None
    assert mapping.requires_human is True


def test_unmapped_field_requires_human():
    mapping = map_field(_field("Favorite programming language"), make_profile())
    assert mapping.candidate_value is None
    assert mapping.requires_human is True
    assert mapping.source == "unmapped"


def test_low_confidence_extracted_value_requires_human_despite_having_a_value():
    profile = make_profile(
        resume=make_resume(
            name=ExtractedField[str](value="Jordan Smith", source="resume", confidence=0.3)
        )
    )
    mapping = map_field(_field("Full Name"), profile)
    assert mapping.candidate_value == "Jordan Smith"
    assert mapping.requires_human is True  # confidence below the 0.7 default threshold


def test_field_with_no_resume_on_file_requires_human():
    profile = make_profile(resume=None)
    mapping = map_field(_field("Email"), profile)
    assert mapping.candidate_value is None
    assert mapping.requires_human is True


def test_map_fields_preserves_order_and_count():
    fields = [_field("Email"), _field("Phone"), _field("Unknown Thing")]
    mappings = map_fields(fields, make_profile())
    assert len(mappings) == 3
    assert mappings[0].field == "email"
    assert mappings[1].field == "phone"
    assert mappings[2].source == "unmapped"

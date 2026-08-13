"""Shared test builders for NormalizedJob / CandidatePreferences."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.jobs.models import NormalizedJob
from app.profile.models import (
    CandidatePreferences,
    CandidateProfile,
    ExtractedField,
    ResumeExtraction,
)


def make_job(**overrides: Any) -> NormalizedJob:
    defaults: dict[str, Any] = dict(
        id="job-1",
        source="test",
        url="https://example.com/jobs/1",
        title="CTO",
        company="Acme Corp",
        location="Bengaluru",
        work_mode="remote",
        salary_min=40.0,
        salary_max=60.0,
        salary_currency="INR",
        description="Lead the engineering organization.",
        required_skills=["Python", "AWS"],
        preferred_skills=["Kubernetes"],
        minimum_experience=10.0,
        maximum_experience=None,
        industry="SaaS",
        employment_type="full_time",
        discovered_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return NormalizedJob(**defaults)


def make_preferences(**overrides: Any) -> CandidatePreferences:
    defaults: dict[str, Any] = dict(
        target_positions=["CTO"],
        preferred_industries=["SaaS"],
        skills_primary=["Python", "AWS", "Kubernetes"],
        skills_secondary=[],
        locations_preferred=["Bengaluru", "Remote"],
        relocation_allowed=False,
        work_mode=["remote", "hybrid"],
        compensation_currency="INR",
        compensation_minimum=30.0,
        compensation_preferred=50.0,
        minimum_match_score=75,
    )
    defaults.update(overrides)
    return CandidatePreferences(**defaults)


def make_resume(**overrides: Any) -> ResumeExtraction:
    defaults: dict[str, Any] = dict(
        source_file="resume.pdf",
        raw_text="Jordan Casey Smith\njordan@example.com",
        email=ExtractedField[str](value="jordan@example.com", source="resume", confidence=0.95),
        experience_years=ExtractedField[float](value=15.0, source="resume", confidence=0.7),
    )
    defaults.update(overrides)
    return ResumeExtraction(**defaults)


def make_profile(**overrides: Any) -> CandidateProfile:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = dict(
        id="default",
        resume=make_resume(),
        preferences=make_preferences(),
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return CandidateProfile(**defaults)

"""Candidate profile schema.

Every field extracted from a document (resume/cover letter) is wrapped in
``ExtractedField`` so downstream consumers (scoring, form-filling) can see
*where* a value came from and *how confident* the extractor was — and so a
field the extractor genuinely couldn't determine is represented as
``value=None, confidence=0.0`` rather than silently omitted or guessed.

This module intentionally has no LLM dependency: Phase 1 extraction is rule
based (see ``app/profile/parser.py``). A future LLM-backed extractor
(Phase 6) fills the same schema — the ``source`` field distinguishes
``"resume"`` (deterministic) from an eventual ``"llm"`` origin.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

FieldSource = Literal["resume", "cover_letter", "config", "unextracted"]


class ExtractedField(BaseModel, Generic[T]):
    value: T | None = None
    source: FieldSource = "unextracted"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @classmethod
    def unextracted(cls) -> ExtractedField[T]:
        return cls(value=None, source="unextracted", confidence=0.0)


class SkillSet(BaseModel):
    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)
    leadership: list[str] = Field(default_factory=list)
    technical: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    ai: list[str] = Field(default_factory=list)

    def all_skills(self) -> list[str]:
        seen: dict[str, None] = {}
        for group in (
            self.primary,
            self.secondary,
            self.leadership,
            self.technical,
            self.platforms,
            self.cloud,
            self.ai,
        ):
            for skill in group:
                seen.setdefault(skill, None)
        return list(seen.keys())


class ResumeExtraction(BaseModel):
    """Structured output of parsing a single resume PDF."""

    source_file: str
    raw_text: str

    name: ExtractedField[str] = Field(default_factory=ExtractedField[str].unextracted)
    email: ExtractedField[str] = Field(default_factory=ExtractedField[str].unextracted)
    phone: ExtractedField[str] = Field(default_factory=ExtractedField[str].unextracted)
    location: ExtractedField[str] = Field(default_factory=ExtractedField[str].unextracted)
    current_title: ExtractedField[str] = Field(default_factory=ExtractedField[str].unextracted)
    experience_years: ExtractedField[float] = Field(
        default_factory=ExtractedField[float].unextracted
    )
    previous_titles: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )
    companies: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )
    industries: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )
    certifications: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )
    education: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )
    languages: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )
    achievements: ExtractedField[list[str]] = Field(
        default_factory=ExtractedField[list[str]].unextracted
    )

    skills: SkillSet = Field(default_factory=SkillSet)


class CandidatePreferences(BaseModel):
    """Job-search preferences — mirrors config/candidate.yaml, editable via API/UI."""

    target_positions: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)

    skills_primary: list[str] = Field(default_factory=list)
    skills_secondary: list[str] = Field(default_factory=list)

    locations_preferred: list[str] = Field(default_factory=list)
    relocation_allowed: bool = False

    work_mode: list[str] = Field(default_factory=list)

    compensation_currency: str = "USD"
    compensation_minimum: float = 0.0
    compensation_preferred: float = 0.0

    companies_prioritize: list[str] = Field(default_factory=list)
    companies_exclude: list[str] = Field(default_factory=list)

    keywords_include: list[str] = Field(default_factory=list)
    keywords_exclude: list[str] = Field(default_factory=list)

    minimum_match_score: int = 75
    maximum_applications_per_day: int = 30

    @classmethod
    def from_yaml(cls, raw: dict) -> CandidatePreferences:
        c = raw.get("candidate", {})
        skills = c.get("skills", {})
        locations = c.get("locations", {})
        compensation = c.get("compensation", {})
        companies = c.get("companies", {})
        keywords = c.get("keywords", {})
        return cls(
            target_positions=c.get("target_positions", []),
            preferred_industries=c.get("preferred_industries", []),
            skills_primary=skills.get("primary", []),
            skills_secondary=skills.get("secondary", []),
            locations_preferred=locations.get("preferred", []),
            relocation_allowed=locations.get("relocation_allowed", False),
            work_mode=c.get("work_mode", []),
            compensation_currency=compensation.get("currency", "USD"),
            compensation_minimum=compensation.get("minimum", 0.0),
            compensation_preferred=compensation.get("preferred", 0.0),
            companies_prioritize=companies.get("prioritize", []),
            companies_exclude=companies.get("exclude", []),
            keywords_include=keywords.get("include", []),
            keywords_exclude=keywords.get("exclude", []),
            minimum_match_score=c.get("minimum_match_score", 75),
            maximum_applications_per_day=c.get("maximum_applications_per_day", 30),
        )


class CandidateProfile(BaseModel):
    """The full candidate profile: parsed documents + search preferences."""

    id: str
    resume: ResumeExtraction | None = None
    cover_letter_text: str | None = None
    cover_letter_source_file: str | None = None
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)
    created_at: datetime
    updated_at: datetime

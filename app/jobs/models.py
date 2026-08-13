"""The common job schema every portal adapter normalizes into (Section 8).

Portal-specific fields must never leak onto this model directly — they go
under ``metadata`` so the matching engine and everything downstream never
needs to know which portal a job came from.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedJob(BaseModel):
    id: str

    external_job_id: str | None = None

    source: str
    url: str

    title: str
    company: str

    location: str | None = None
    work_mode: str | None = None  # "remote" | "hybrid" | "onsite" | None (unknown)

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None

    description: str = ""

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    minimum_experience: float | None = None
    maximum_experience: float | None = None

    industry: str | None = None

    employment_type: str | None = None

    posted_at: datetime | None = None
    discovered_at: datetime

    application_type: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

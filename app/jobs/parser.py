"""Portal-agnostic job normalization.

A concrete portal adapter (Phase 7+) is responsible for producing a raw
dict in the shape this module expects and calling ``normalize_job``; this
keeps the "turn one portal's page/API response into our common schema"
logic in exactly one place rather than duplicated per adapter.

The job id is derived deterministically from ``(source, external_job_id or
url)`` via uuid5 — the same job seen twice (e.g. re-discovered on a later
run) always normalizes to the same id, which is what Section 14's
duplicate-detection constraint (``UNIQUE(source, external_job_id)``) relies
on.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.jobs.models import NormalizedJob

_KNOWN_FIELDS = {
    "external_job_id",
    "url",
    "title",
    "company",
    "location",
    "work_mode",
    "salary_min",
    "salary_max",
    "salary_currency",
    "description",
    "required_skills",
    "preferred_skills",
    "minimum_experience",
    "maximum_experience",
    "industry",
    "employment_type",
    "posted_at",
    "application_type",
}

_REQUIRED_FIELDS = ("url", "title", "company")


def _stable_job_id(source: str, external_job_id: str | None, url: str) -> str:
    key = f"{source}:{external_job_id}" if external_job_id else f"{source}:{url}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def normalize_job(
    raw: dict[str, Any],
    *,
    source: str,
    discovered_at: datetime | None = None,
) -> NormalizedJob:
    missing = [f for f in _REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        raise ValueError(f"raw job is missing required field(s): {', '.join(missing)}")

    external_job_id = raw.get("external_job_id")
    metadata = {k: v for k, v in raw.items() if k not in _KNOWN_FIELDS}

    return NormalizedJob(
        id=_stable_job_id(source, external_job_id, raw["url"]),
        external_job_id=external_job_id,
        source=source,
        url=raw["url"],
        title=raw["title"],
        company=raw["company"],
        location=raw.get("location"),
        work_mode=raw.get("work_mode"),
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        salary_currency=raw.get("salary_currency"),
        description=raw.get("description", ""),
        required_skills=list(raw.get("required_skills") or []),
        preferred_skills=list(raw.get("preferred_skills") or []),
        minimum_experience=raw.get("minimum_experience"),
        maximum_experience=raw.get("maximum_experience"),
        industry=raw.get("industry"),
        employment_type=raw.get("employment_type"),
        posted_at=raw.get("posted_at"),
        discovered_at=discovered_at or datetime.now(UTC),
        application_type=raw.get("application_type"),
        metadata=metadata,
    )

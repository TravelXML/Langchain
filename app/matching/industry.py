"""Industry scoring (Section 15)."""

from __future__ import annotations


def score_industry(
    job_industry: str | None,
    preferred_industries: list[str],
    *,
    weight: float,
) -> float:
    if not preferred_industries:
        # Candidate has no stated industry preference.
        return weight

    if job_industry is None:
        # Job didn't disclose its industry — mild neutral credit, not a
        # penalty for missing data.
        return round(weight * 0.7, 2)

    job_industry_lower = job_industry.lower()
    if any(pref.lower() in job_industry_lower for pref in preferred_industries):
        return weight

    return round(weight * 0.2, 2)

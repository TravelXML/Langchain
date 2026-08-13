"""Location / work-mode scoring (Section 15)."""

from __future__ import annotations


def _location_matches(job_location: str | None, preferred_locations: list[str]) -> bool:
    if job_location is None or not preferred_locations:
        return False
    job_location_lower = job_location.lower()
    return any(pref.lower() in job_location_lower for pref in preferred_locations)


def score_location(
    job_location: str | None,
    job_work_mode: str | None,
    *,
    preferred_locations: list[str],
    preferred_work_modes: list[str],
    relocation_allowed: bool,
    weight: float,
) -> float:
    if job_work_mode is None:
        # Unknown work mode — fall back to location match alone.
        return weight if _location_matches(job_location, preferred_locations) else weight * 0.5

    if job_work_mode == "remote" and "remote" in preferred_work_modes:
        return weight

    if job_work_mode not in preferred_work_modes:
        # Candidate doesn't want this work mode at all (e.g. onsite-only job,
        # remote-only candidate).
        if relocation_allowed and _location_matches(job_location, preferred_locations):
            return round(weight * 0.5, 2)
        return round(weight * 0.1, 2)

    if _location_matches(job_location, preferred_locations):
        return weight

    if relocation_allowed:
        return round(weight * 0.6, 2)

    return round(weight * 0.2, 2)

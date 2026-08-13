"""Compensation scoring (Section 15).

Deterministic only — never invents a salary figure the job didn't state
(Section 17: fabricated compensation is explicitly prohibited).
"""

from __future__ import annotations


def score_salary(
    job_salary_min: float | None,
    job_salary_max: float | None,
    job_currency: str | None,
    candidate_minimum: float,
    candidate_preferred: float,
    candidate_currency: str,
    *,
    weight: float,
) -> float:
    reference = job_salary_max if job_salary_max is not None else job_salary_min
    if reference is None:
        # Job didn't disclose salary — can't penalize it for that.
        return weight

    if job_currency is not None and job_currency != candidate_currency:
        # Different currencies without conversion data: can't compare
        # confidently, so score neutrally rather than guess an FX rate.
        return round(weight * 0.5, 2)

    if candidate_preferred > 0 and reference >= candidate_preferred:
        return weight

    if candidate_minimum > 0 and reference >= candidate_minimum:
        if candidate_preferred > candidate_minimum:
            position = (reference - candidate_minimum) / (candidate_preferred - candidate_minimum)
        else:
            position = 1.0
        return round(weight * (0.6 + 0.4 * min(position, 1.0)), 2)

    if candidate_minimum <= 0:
        # No stated minimum to compare against.
        return weight

    ratio = max(reference / candidate_minimum, 0.0)
    return round(weight * ratio * 0.6, 2)

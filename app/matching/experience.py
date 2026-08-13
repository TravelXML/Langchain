"""Experience-years scoring (Section 15)."""

from __future__ import annotations


def score_experience(
    candidate_years: float | None,
    minimum_experience: float | None,
    maximum_experience: float | None,
    *,
    weight: float,
) -> float:
    if minimum_experience is None and maximum_experience is None:
        # Job states no requirement — nothing to penalize.
        return weight

    if candidate_years is None:
        # Unknown candidate experience against a stated requirement: we
        # can't fairly score this, so give partial credit rather than
        # silently guessing either way (see Section 20's confidence rule).
        return round(weight * 0.5, 2)

    if minimum_experience is not None and candidate_years < minimum_experience:
        ratio = max(candidate_years / minimum_experience, 0.0) if minimum_experience > 0 else 0.0
        return round(weight * ratio, 2)

    if maximum_experience is not None and candidate_years > maximum_experience * 1.5:
        # Significantly overqualified — mild penalty, not a rejection.
        return round(weight * 0.8, 2)

    return weight

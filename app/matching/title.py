"""Title / seniority matching (Section 13/15).

Title families group known synonyms (e.g. "CTO" and "Chief Technology
Officer") so a candidate's target positions match a job title regardless of
exact wording. Titles outside every known family fall back to token-overlap
similarity (see ``semantic.py``) rather than scoring zero outright — a
completely unrecognized title shouldn't be treated the same as an
obviously unrelated one.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.matching.semantic import token_overlap_ratio

# family name -> synonym titles (the family name itself is always included).
TITLE_FAMILIES: dict[str, list[str]] = {
    "CTO": [
        "chief technology officer",
        "chief technical officer",
        "technology head",
        "head of technology",
        "vp technology",
        "technology director",
    ],
    "VP Engineering": [
        "vice president engineering",
        "vp of engineering",
        "vp eng",
    ],
    "Head of Engineering": [
        "engineering head",
        "director of engineering",
    ],
    "IT Director": [
        "director of it",
        "director, it",
    ],
}

_TITLE_TO_FAMILY: dict[str, str] = {name.lower(): name for name in TITLE_FAMILIES} | {
    synonym: name for name, synonyms in TITLE_FAMILIES.items() for synonym in synonyms
}

# Below this token-overlap ratio, an unrecognized title is treated as
# unrelated rather than given partial credit.
_PARTIAL_MATCH_FLOOR = 0.34


def title_family(title: str) -> str | None:
    return _TITLE_TO_FAMILY.get(title.strip().lower())


class TitleMatchResult(BaseModel):
    score: float
    matched_family: str | None
    matched_target: str | None


def match_title(
    target_positions: list[str],
    job_title: str,
    *,
    weight: float,
) -> TitleMatchResult:
    if not target_positions:
        # No stated preference — can't fault the job for it, treat neutrally.
        return TitleMatchResult(score=weight, matched_family=None, matched_target=None)

    job_family = title_family(job_title)

    if job_family is not None:
        for target in target_positions:
            if title_family(target) == job_family:
                return TitleMatchResult(
                    score=weight, matched_family=job_family, matched_target=target
                )

    best_ratio = 0.0
    best_target: str | None = None
    for target in target_positions:
        ratio = token_overlap_ratio(target, job_title)
        if ratio > best_ratio:
            best_ratio, best_target = ratio, target

    if best_ratio < _PARTIAL_MATCH_FLOOR:
        return TitleMatchResult(score=0.0, matched_family=job_family, matched_target=None)

    return TitleMatchResult(
        score=round(weight * best_ratio, 2), matched_family=job_family, matched_target=best_target
    )

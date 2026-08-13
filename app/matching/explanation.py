"""Deterministic, template-based score explanations (Section 15).

Not LLM-generated: Phase 2 has no LLM available yet, and a templated
explanation is fully reproducible and testable. An LLM-polished version of
this text is a reasonable Phase 6+ enhancement, but the underlying facts
(scores, matched/missing skills) must always come from here, never invented.
"""

from __future__ import annotations

from app.matching.models import Recommendation, ScoreBreakdown
from app.matching.title import TitleMatchResult


def build_explanation(
    *,
    breakdown: ScoreBreakdown,
    overall_score: float,
    recommendation: Recommendation,
    title_match: TitleMatchResult,
    matched_skills: list[str],
    missing_skills: list[str],
) -> str:
    parts: list[str] = []

    if title_match.matched_family:
        parts.append(f"title matches '{title_match.matched_family}' ({breakdown.title:g} pts)")
    elif title_match.matched_target:
        parts.append(f"title partially matches '{title_match.matched_target}'")
    else:
        parts.append(f"title does not match target positions ({breakdown.title:g} pts)")

    if matched_skills:
        parts.append(f"{len(matched_skills)} skill(s) matched: {', '.join(matched_skills)}")
    if missing_skills:
        parts.append(f"missing: {', '.join(missing_skills)}")

    parts.append(f"experience {breakdown.experience:g} pts")
    parts.append(f"industry {breakdown.industry:g} pts")
    parts.append(f"location {breakdown.location:g} pts")
    parts.append(f"compensation {breakdown.compensation:g} pts")

    summary = "; ".join(parts)
    return f"{summary}. Overall {overall_score:g}/100 -> {recommendation}."

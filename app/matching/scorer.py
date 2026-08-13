"""Combined weighted job-candidate scorer (Section 15).

Pure rule-based composition of the individual signal scorers — no LLM, no
embeddings (those are Phase 6/38 additions layered on top later without
changing this function's signature).
"""

from __future__ import annotations

from app.jobs.models import NormalizedJob
from app.matching.experience import score_experience
from app.matching.explanation import build_explanation
from app.matching.industry import score_industry
from app.matching.location import score_location
from app.matching.models import (
    MatchResult,
    ScoreBreakdown,
    ScoringThresholds,
    ScoringWeights,
    load_scoring_thresholds,
    load_scoring_weights,
)
from app.matching.salary import score_salary
from app.matching.skills import match_skills
from app.matching.title import match_title
from app.profile.models import CandidatePreferences


def score_job(
    job: NormalizedJob,
    *,
    preferences: CandidatePreferences,
    candidate_skills: list[str],
    candidate_experience_years: float | None,
    weights: ScoringWeights | None = None,
    thresholds: ScoringThresholds | None = None,
) -> MatchResult:
    weights = weights or load_scoring_weights()
    thresholds = thresholds or load_scoring_thresholds()

    title_match = match_title(preferences.target_positions, job.title, weight=weights.title)

    skill_match = match_skills(
        candidate_skills,
        job.required_skills,
        job.preferred_skills,
        weight=weights.skills,
    )

    experience_score = score_experience(
        candidate_experience_years,
        job.minimum_experience,
        job.maximum_experience,
        weight=weights.experience,
    )

    industry_score = score_industry(
        job.industry, preferences.preferred_industries, weight=weights.industry
    )

    location_score = score_location(
        job.location,
        job.work_mode,
        preferred_locations=preferences.locations_preferred,
        preferred_work_modes=preferences.work_mode,
        relocation_allowed=preferences.relocation_allowed,
        weight=weights.location,
    )

    compensation_score = score_salary(
        job.salary_min,
        job.salary_max,
        job.salary_currency,
        preferences.compensation_minimum,
        preferences.compensation_preferred,
        preferences.compensation_currency,
        weight=weights.compensation,
    )

    breakdown = ScoreBreakdown(
        title=title_match.score,
        skills=skill_match.score,
        experience=experience_score,
        industry=industry_score,
        location=location_score,
        compensation=compensation_score,
    )

    overall_score = round(
        breakdown.title
        + breakdown.skills
        + breakdown.experience
        + breakdown.industry
        + breakdown.location
        + breakdown.compensation,
        2,
    )

    recommendation = thresholds.recommendation_for(overall_score)

    reason = build_explanation(
        breakdown=breakdown,
        overall_score=overall_score,
        recommendation=recommendation,
        title_match=title_match,
        matched_skills=skill_match.matched,
        missing_skills=skill_match.missing,
    )

    return MatchResult(
        overall_score=overall_score,
        breakdown=breakdown,
        matched_skills=skill_match.matched,
        missing_skills=skill_match.missing,
        reason=reason,
        recommendation=recommendation,
    )

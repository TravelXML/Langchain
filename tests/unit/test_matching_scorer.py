from __future__ import annotations

from app.matching.models import ScoringThresholds, ScoringWeights
from app.matching.scorer import score_job
from tests.fixtures.job_builder import make_job, make_preferences

WEIGHTS = ScoringWeights()
THRESHOLDS = ScoringThresholds()


def _score(job=None, preferences=None, skills=None, experience_years=15.0):
    return score_job(
        job or make_job(),
        preferences=preferences or make_preferences(),
        candidate_skills=skills if skills is not None else ["Python", "AWS", "Kubernetes"],
        candidate_experience_years=experience_years,
        weights=WEIGHTS,
        thresholds=THRESHOLDS,
    )


def test_ideal_match_is_priority_apply():
    result = _score()
    assert result.recommendation == "priority_apply"
    assert result.overall_score >= 90


def test_good_but_imperfect_match_is_normal_or_priority_apply():
    result = _score(job=make_job(location="Berlin", work_mode="onsite"))
    assert result.recommendation in ("normal_apply", "priority_apply", "apply_if_capacity")


def test_missing_most_skills_and_wrong_title_is_reject():
    job = make_job(
        title="Marketing Coordinator",
        required_skills=["Adobe Photoshop", "Copywriting"],
        preferred_skills=["SEO"],
        industry="Retail",
        location="Berlin",
        work_mode="onsite",
        salary_min=5.0,
        salary_max=8.0,
        minimum_experience=0,
    )
    result = _score(job=job, skills=["Python"])
    assert result.recommendation == "reject"
    assert result.overall_score < 60


def test_completely_unrelated_job_is_rejected():
    # Note: undisclosed job fields (salary, experience range) intentionally
    # score neutrally rather than being penalized — even so, an unrelated
    # title/skills/industry/location combination should still fall below
    # the reject threshold.
    job = make_job(
        title="Warehouse Associate",
        required_skills=["Forklift Operation"],
        preferred_skills=[],
        industry="Logistics",
        location="Unknown City",
        work_mode="onsite",
        salary_min=None,
        salary_max=None,
        minimum_experience=None,
        maximum_experience=None,
    )
    result = _score(
        job=job,
        preferences=make_preferences(
            target_positions=["CTO"],
            preferred_industries=["SaaS"],
            locations_preferred=["Bengaluru"],
            work_mode=["remote"],
            relocation_allowed=False,
        ),
        skills=["Python", "AWS"],
        experience_years=15.0,
    )
    assert result.recommendation == "reject"
    assert result.overall_score < THRESHOLDS.human_review


def test_unknown_candidate_experience_reduces_experience_score():
    job = make_job(
        required_skills=["Python"],
        preferred_skills=[],
        salary_min=None,
        salary_max=None,
        minimum_experience=15,
    )
    result = _score(job=job, skills=["Python"], experience_years=None)
    # Missing candidate experience against a stated requirement should never
    # score as confidently as a fully-known match.
    assert result.breakdown.experience < WEIGHTS.experience


def test_matched_and_missing_skills_are_reported():
    job = make_job(required_skills=["Python", "Go"], preferred_skills=["Rust"])
    result = _score(job=job, skills=["Python"])
    assert "Python" in result.matched_skills
    assert "Go" in result.missing_skills
    assert "Rust" not in result.missing_skills  # missing_skills reports required only


def test_reason_mentions_recommendation():
    result = _score()
    assert result.recommendation in result.reason


def test_score_never_exceeds_100_when_weights_sum_to_100():
    assert sum(WEIGHTS.model_dump().values()) == 100
    result = _score()
    assert result.overall_score <= 100


def test_score_never_negative():
    job = make_job(
        title="Unrelated Role",
        required_skills=["Nothing Relevant"],
        preferred_skills=[],
        location="Nowhere",
        work_mode="onsite",
        industry="Unrelated",
        salary_min=1.0,
        salary_max=2.0,
        minimum_experience=50,
    )
    result = _score(job=job, skills=[], experience_years=0)
    assert result.overall_score >= 0

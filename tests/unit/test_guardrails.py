from __future__ import annotations

from app.guardrails.engine import run_guardrails
from app.guardrails.models import GuardrailContext, GuardrailDecision
from app.guardrails.policy import (
    check_company_daily_limit,
    check_daily_limit,
    check_duplicate_application,
    check_excluded_company,
    check_excluded_location,
    check_excluded_role,
    check_experience_mismatch,
    check_mandatory_fields,
    check_minimum_salary,
    check_minimum_score,
    check_resume_validation,
    check_work_authorization,
)
from app.matching.models import MatchResult, ScoreBreakdown
from app.profile.models import ExtractedField
from tests.fixtures.job_builder import make_job, make_preferences, make_profile

_BREAKDOWN = ScoreBreakdown(
    title=25, skills=30, experience=15, industry=10, location=10, compensation=10
)


def _match(**overrides) -> MatchResult:
    defaults = dict(
        overall_score=90, breakdown=_BREAKDOWN, reason="fit", recommendation="normal_apply"
    )
    defaults.update(overrides)
    return MatchResult(**defaults)


def _ctx(**overrides) -> GuardrailContext:
    defaults = dict(job=make_job(), match=_match(), profile=make_profile())
    defaults.update(overrides)
    return GuardrailContext(**defaults)


# --- Section 17's 7 required scenarios -------------------------------------


def test_low_score_blocked():
    ctx = _ctx(match=_match(overall_score=50, recommendation="normal_apply"))
    result = check_minimum_score(ctx)
    assert result.decision == GuardrailDecision.BLOCK


def test_duplicate_blocked():
    job = make_job(id="job-42")
    ctx = _ctx(job=job, already_applied_job_ids={"job-42"})
    result = check_duplicate_application(ctx)
    assert result.decision == GuardrailDecision.BLOCK


def test_salary_mismatch_blocked():
    job = make_job(salary_min=5, salary_max=10, salary_currency="INR")
    profile = make_profile(preferences=make_preferences(compensation_minimum=30))
    ctx = _ctx(job=job, profile=profile)
    result = check_minimum_salary(ctx)
    assert result.decision == GuardrailDecision.BLOCK


def test_excluded_company_blocked():
    job = make_job(company="Blacklisted Inc")
    profile = make_profile(preferences=make_preferences(companies_exclude=["Blacklisted Inc"]))
    ctx = _ctx(job=job, profile=profile)
    result = check_excluded_company(ctx)
    assert result.decision == GuardrailDecision.BLOCK


def test_unknown_work_authorization_requires_human_input():
    profile = make_profile(preferences=make_preferences(work_authorization=None))
    ctx = _ctx(profile=profile)
    result = check_work_authorization(ctx)
    assert result.decision == GuardrailDecision.HUMAN_INPUT_REQUIRED


def test_daily_limit_blocked():
    ctx = _ctx(applications_today=30)
    result = check_daily_limit(ctx, system_limit=30)
    assert result.decision == GuardrailDecision.BLOCK


def test_fabricated_experience_answer_prevented():
    """The concrete test for Section 17's "never invent candidate
    information": experience was never extracted from the resume
    (source="unextracted"), and the job states a minimum — the guardrail
    must ask a human rather than assume either way."""
    profile = make_profile(
        resume=make_profile().resume.model_copy(
            update={"experience_years": ExtractedField[float].unextracted()}
        )
    )
    ctx = _ctx(job=make_job(minimum_experience=10), profile=profile)
    result = check_experience_mismatch(ctx)
    assert result.decision == GuardrailDecision.HUMAN_INPUT_REQUIRED
    assert profile.resume.experience_years.source == "unextracted"


# --- Additional coverage -----------------------------------------------


def test_low_score_not_blocked_when_already_pending_human_review():
    """A stricter personal minimum_match_score must not silently veto a job
    the scorer already flagged for human review (Section 19's safety net)."""
    ctx = _ctx(
        match=_match(overall_score=66, recommendation="human_review"),
        profile=make_profile(preferences=make_preferences(minimum_match_score=75)),
    )
    result = check_minimum_score(ctx)
    assert result.decision == GuardrailDecision.ALLOW


def test_excluded_role_blocked_on_title_keyword():
    job = make_job(title="Senior Sales Associate")
    profile = make_profile(preferences=make_preferences(keywords_exclude=["Sales"]))
    ctx = _ctx(job=job, profile=profile)
    assert check_excluded_role(ctx).decision == GuardrailDecision.BLOCK


def test_excluded_location_blocked():
    job = make_job(location="Berlin, Germany")
    profile = make_profile(preferences=make_preferences(locations_excluded=["Berlin"]))
    ctx = _ctx(job=job, profile=profile)
    assert check_excluded_location(ctx).decision == GuardrailDecision.BLOCK


def test_company_daily_limit_blocked():
    ctx = _ctx(applications_today_for_company=2)
    result = check_company_daily_limit(ctx, system_limit=2)
    assert result.decision == GuardrailDecision.BLOCK


def test_resume_validation_blocked_without_resume():
    ctx = _ctx(profile=make_profile(resume=None))
    assert check_resume_validation(ctx).decision == GuardrailDecision.BLOCK


def test_mandatory_fields_blocked_without_email():
    resume = make_profile().resume.model_copy(update={"email": ExtractedField[str].unextracted()})
    ctx = _ctx(profile=make_profile(resume=resume))
    assert check_mandatory_fields(ctx).decision == GuardrailDecision.BLOCK


def test_experience_grossly_underqualified_blocked():
    resume = make_profile().resume.model_copy(
        update={
            "experience_years": ExtractedField[float](value=1.0, source="resume", confidence=0.7)
        }
    )
    ctx = _ctx(job=make_job(minimum_experience=10), profile=make_profile(resume=resume))
    assert check_experience_mismatch(ctx).decision == GuardrailDecision.BLOCK


def test_minimum_salary_allows_undisclosed_salary():
    job = make_job(salary_min=None, salary_max=None)
    ctx = _ctx(job=job)
    assert check_minimum_salary(ctx).decision == GuardrailDecision.ALLOW


def test_minimum_salary_allows_currency_mismatch_rather_than_blocking():
    job = make_job(salary_min=5, salary_max=8, salary_currency="USD")
    profile = make_profile(
        preferences=make_preferences(compensation_currency="INR", compensation_minimum=30)
    )
    ctx = _ctx(job=job, profile=profile)
    assert check_minimum_salary(ctx).decision == GuardrailDecision.ALLOW


# --- Engine orchestration -------------------------------------------------


def test_engine_block_takes_precedence_over_human_input():
    # Excluded company (BLOCK) + unknown work authorization (HUMAN_INPUT) at
    # the same time — overall must be BLOCK.
    job = make_job(company="Blacklisted Inc")
    profile = make_profile(
        preferences=make_preferences(companies_exclude=["Blacklisted Inc"], work_authorization=None)
    )
    report = run_guardrails(_ctx(job=job, profile=profile))
    assert report.decision == GuardrailDecision.BLOCK


def test_engine_allow_when_everything_passes():
    profile = make_profile(preferences=make_preferences(work_authorization="citizen"))
    report = run_guardrails(_ctx(profile=profile))
    assert report.decision == GuardrailDecision.ALLOW
    assert report.blocking_reasons == []
    assert report.human_input_reasons == []


def test_engine_human_input_when_only_soft_issue_present():
    profile = make_profile(preferences=make_preferences(work_authorization=None))
    report = run_guardrails(_ctx(profile=profile))
    assert report.decision == GuardrailDecision.HUMAN_INPUT_REQUIRED
    assert any("work" in r for r in report.human_input_reasons)

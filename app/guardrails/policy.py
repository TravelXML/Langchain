"""Deterministic guardrail checks (Section 17).

Each function inspects a ``GuardrailContext`` and returns exactly one
``GuardrailCheckResult`` — no LLM, no fuzzy judgment calls. Where a value
is genuinely unknown (candidate experience never extracted, work
authorization never provided), the check returns
``HUMAN_INPUT_REQUIRED`` rather than assuming an answer either way —
that's the concrete, testable form Section 17's "never invent candidate
information" takes here.
"""

from __future__ import annotations

from app.guardrails.models import GuardrailCheckResult, GuardrailContext, GuardrailDecision

_ALLOW = GuardrailDecision.ALLOW
_BLOCK = GuardrailDecision.BLOCK
_HUMAN = GuardrailDecision.HUMAN_INPUT_REQUIRED


def check_minimum_score(ctx: GuardrailContext) -> GuardrailCheckResult:
    """The candidate's personal score floor — stricter than, and independent
    of, the scorer's own recommendation thresholds (``config/scoring.yaml``).

    Deliberately does *not* apply to jobs the scorer already routed to
    ``human_review``: that band is itself a deliberate safety net (Section
    19), and a stricter personal minimum shouldn't silently veto a job
    before a human ever gets to weigh in on it. It only downgrades jobs the
    scorer would otherwise have queued outright.
    """
    if ctx.match.recommendation == "human_review":
        return GuardrailCheckResult(
            rule="minimum_match_score", decision=_ALLOW, reason="pending human review"
        )

    threshold = ctx.profile.preferences.minimum_match_score
    if ctx.match.overall_score < threshold:
        return GuardrailCheckResult(
            rule="minimum_match_score",
            decision=_BLOCK,
            reason=f"score {ctx.match.overall_score:g} is below the minimum {threshold}",
        )
    return GuardrailCheckResult(rule="minimum_match_score", decision=_ALLOW, reason="score OK")


def check_daily_limit(ctx: GuardrailContext, *, system_limit: int) -> GuardrailCheckResult:
    # The stricter of the system-wide safety limit (config/automation.yaml,
    # Section 49 — "guardrails must enforce these even if the supervisor
    # requests otherwise") and the candidate's own preference wins.
    effective_limit = min(system_limit, ctx.profile.preferences.maximum_applications_per_day)
    if ctx.applications_today >= effective_limit:
        return GuardrailCheckResult(
            rule="maximum_daily_applications",
            decision=_BLOCK,
            reason=f"{ctx.applications_today} applications today already reached "
            f"the limit of {effective_limit}",
        )
    return GuardrailCheckResult(rule="maximum_daily_applications", decision=_ALLOW, reason="OK")


def check_company_daily_limit(ctx: GuardrailContext, *, system_limit: int) -> GuardrailCheckResult:
    if ctx.applications_today_for_company >= system_limit:
        return GuardrailCheckResult(
            rule="maximum_company_applications",
            decision=_BLOCK,
            reason=f"{ctx.applications_today_for_company} applications to "
            f"{ctx.job.company} today already reached the limit of {system_limit}",
        )
    return GuardrailCheckResult(rule="maximum_company_applications", decision=_ALLOW, reason="OK")


def check_excluded_company(ctx: GuardrailContext) -> GuardrailCheckResult:
    excluded = {c.lower() for c in ctx.profile.preferences.companies_exclude}
    if ctx.job.company.lower() in excluded:
        return GuardrailCheckResult(
            rule="excluded_companies",
            decision=_BLOCK,
            reason=f"{ctx.job.company} is on the excluded-companies list",
        )
    return GuardrailCheckResult(rule="excluded_companies", decision=_ALLOW, reason="not excluded")


def check_excluded_role(ctx: GuardrailContext) -> GuardrailCheckResult:
    haystack = f"{ctx.job.title} {ctx.job.description}".lower()
    for keyword in ctx.profile.preferences.keywords_exclude:
        if keyword.lower() in haystack:
            return GuardrailCheckResult(
                rule="excluded_roles",
                decision=_BLOCK,
                reason=f"job matches excluded keyword '{keyword}'",
            )
    return GuardrailCheckResult(rule="excluded_roles", decision=_ALLOW, reason="not excluded")


def check_excluded_location(ctx: GuardrailContext) -> GuardrailCheckResult:
    if not ctx.job.location:
        return GuardrailCheckResult(rule="excluded_locations", decision=_ALLOW, reason="unknown")
    location_lower = ctx.job.location.lower()
    for excluded in ctx.profile.preferences.locations_excluded:
        if excluded.lower() in location_lower:
            return GuardrailCheckResult(
                rule="excluded_locations",
                decision=_BLOCK,
                reason=f"{ctx.job.location} matches excluded location '{excluded}'",
            )
    return GuardrailCheckResult(rule="excluded_locations", decision=_ALLOW, reason="not excluded")


def check_minimum_salary(ctx: GuardrailContext) -> GuardrailCheckResult:
    prefs = ctx.profile.preferences
    reference = ctx.job.salary_max if ctx.job.salary_max is not None else ctx.job.salary_min

    if reference is None or prefs.compensation_minimum <= 0:
        return GuardrailCheckResult(rule="minimum_salary", decision=_ALLOW, reason="not disclosed")

    if ctx.job.salary_currency and ctx.job.salary_currency != prefs.compensation_currency:
        # Can't compare across currencies without conversion data — this is
        # a soft signal (the scorer already reflects it), not a hard block.
        return GuardrailCheckResult(
            rule="minimum_salary", decision=_ALLOW, reason="currency mismatch, cannot compare"
        )

    if reference < prefs.compensation_minimum:
        return GuardrailCheckResult(
            rule="minimum_salary",
            decision=_BLOCK,
            reason=f"{reference:g} {ctx.job.salary_currency or prefs.compensation_currency} is "
            f"below the minimum {prefs.compensation_minimum:g}",
        )
    return GuardrailCheckResult(rule="minimum_salary", decision=_ALLOW, reason="meets minimum")


def check_experience_mismatch(ctx: GuardrailContext) -> GuardrailCheckResult:
    """Also the concrete "never fabricate experience" guardrail.

    If the job requires a minimum tenure and the resume parser never
    determined the candidate's years of experience (``source ==
    "unextracted"``, per Section 6/17), this returns
    ``HUMAN_INPUT_REQUIRED`` — it never assumes the candidate does or
    doesn't qualify.
    """
    minimum = ctx.job.minimum_experience
    if minimum is None:
        return GuardrailCheckResult(rule="experience_mismatch", decision=_ALLOW, reason="no floor")

    resume = ctx.profile.resume
    candidate_years = resume.experience_years.value if resume else None

    if candidate_years is None:
        return GuardrailCheckResult(
            rule="experience_mismatch",
            decision=_HUMAN,
            reason="candidate years of experience were never extracted from the resume; "
            "cannot confirm eligibility without guessing",
        )

    if candidate_years < minimum * 0.5:
        return GuardrailCheckResult(
            rule="experience_mismatch",
            decision=_BLOCK,
            reason=f"{candidate_years:g} years is well below the {minimum:g}-year requirement",
        )
    return GuardrailCheckResult(rule="experience_mismatch", decision=_ALLOW, reason="meets floor")


def check_work_authorization(ctx: GuardrailContext) -> GuardrailCheckResult:
    if ctx.profile.preferences.work_authorization is None:
        return GuardrailCheckResult(
            rule="required_work_authorization",
            decision=_HUMAN,
            reason="candidate has not stated a work-authorization status "
            "(Section 18: never inferred automatically)",
        )
    return GuardrailCheckResult(
        rule="required_work_authorization", decision=_ALLOW, reason="status on file"
    )


def check_duplicate_application(ctx: GuardrailContext) -> GuardrailCheckResult:
    if ctx.job.id in ctx.already_applied_job_ids:
        return GuardrailCheckResult(
            rule="duplicate_application",
            decision=_BLOCK,
            reason="an application for this job already exists",
        )
    return GuardrailCheckResult(rule="duplicate_application", decision=_ALLOW, reason="new")


def check_resume_validation(ctx: GuardrailContext) -> GuardrailCheckResult:
    if ctx.profile.resume is None or not ctx.profile.resume.raw_text.strip():
        return GuardrailCheckResult(
            rule="resume_validation",
            decision=_BLOCK,
            reason="no parsed resume on file — import a resume before applying",
        )
    return GuardrailCheckResult(rule="resume_validation", decision=_ALLOW, reason="resume on file")


def check_mandatory_fields(ctx: GuardrailContext) -> GuardrailCheckResult:
    resume = ctx.profile.resume
    if resume is None or not resume.email.value:
        return GuardrailCheckResult(
            rule="mandatory_fields",
            decision=_BLOCK,
            reason="candidate email could not be determined",
        )
    return GuardrailCheckResult(rule="mandatory_fields", decision=_ALLOW, reason="present")


ALL_CHECKS = (
    check_minimum_score,
    check_excluded_company,
    check_excluded_role,
    check_excluded_location,
    check_minimum_salary,
    check_experience_mismatch,
    check_work_authorization,
    check_duplicate_application,
    check_resume_validation,
    check_mandatory_fields,
)

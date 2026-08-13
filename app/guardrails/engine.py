"""Guardrail orchestration: run every check, aggregate to one decision.

Precedence is BLOCK > HUMAN_INPUT_REQUIRED > ALLOW — a single blocking
violation vetoes the application outright even if another check would only
have asked for human input, and the supervisor must never be able to
override that (Section 23: "Supervisor SHOULD NOT ... bypass policy rules
[or] override guardrails").
"""

from __future__ import annotations

from app.core.config import get_yaml_config_loader
from app.guardrails.models import (
    GuardrailCheckResult,
    GuardrailContext,
    GuardrailDecision,
    GuardrailReport,
)
from app.guardrails.policy import ALL_CHECKS, check_company_daily_limit, check_daily_limit


def run_guardrails(ctx: GuardrailContext) -> GuardrailReport:
    automation = get_yaml_config_loader().load("automation")
    limits = automation.get("limits", {})
    daily_limit = limits.get("applications_per_day", 30)
    company_limit = limits.get("applications_per_company_per_day", 2)

    results: list[GuardrailCheckResult] = [
        check_daily_limit(ctx, system_limit=daily_limit),
        check_company_daily_limit(ctx, system_limit=company_limit),
        *(check(ctx) for check in ALL_CHECKS),
    ]

    if any(r.decision == GuardrailDecision.BLOCK for r in results):
        overall = GuardrailDecision.BLOCK
    elif any(r.decision == GuardrailDecision.HUMAN_INPUT_REQUIRED for r in results):
        overall = GuardrailDecision.HUMAN_INPUT_REQUIRED
    else:
        overall = GuardrailDecision.ALLOW

    return GuardrailReport(decision=overall, checks=results)

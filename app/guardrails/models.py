"""Guardrail schema (Section 17).

Every rule returns exactly one of three decisions — never a raw bool, so
call sites can't accidentally conflate "blocked" with "needs a human" (the
whole point of Section 17/18's fabrication-prevention rules is that those
are *not* the same outcome).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.jobs.models import NormalizedJob
from app.matching.models import MatchResult
from app.profile.models import CandidateProfile


class GuardrailDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    HUMAN_INPUT_REQUIRED = "human_input_required"


class GuardrailCheckResult(BaseModel):
    rule: str
    decision: GuardrailDecision
    reason: str


class GuardrailReport(BaseModel):
    decision: GuardrailDecision
    checks: list[GuardrailCheckResult]

    @property
    def blocking_reasons(self) -> list[str]:
        return [c.reason for c in self.checks if c.decision == GuardrailDecision.BLOCK]

    @property
    def human_input_reasons(self) -> list[str]:
        return [
            c.reason for c in self.checks if c.decision == GuardrailDecision.HUMAN_INPUT_REQUIRED
        ]


class GuardrailContext(BaseModel):
    """Everything a guardrail check might need.

    ``applications_today``/``applications_today_for_company``/
    ``already_applied_job_ids`` default to zero/empty because no real
    ``applications`` table exists yet (Phase 5+ records actual
    submissions) — the checks that use them are fully implemented and
    tested, they just have nothing to count against until then.
    """

    job: NormalizedJob
    match: MatchResult
    profile: CandidateProfile

    applications_today: int = 0
    applications_today_for_company: int = 0
    already_applied_job_ids: set[str] = Field(default_factory=set)

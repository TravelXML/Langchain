"""LangGraph state schema (Section 5).

Scoped to what Phase 3 actually implements — discovery through
reject/queue routing. Application-lifecycle fields from the full spec
(``current_job``, ``selected_resume``, ``generated_answers``,
``application_status``, ``retry_count``, ...) are added when the phases
that use them (5+) land, rather than declared unused up front.

Fields annotated with a reducer (``operator.add``) accumulate across
parallel node invocations — e.g. every mock portal's ``discover_portal``
call appends to the same ``discovered_jobs`` list instead of overwriting
each other (Section 24's fan-out/aggregate pattern). Unannotated fields
are last-write-wins, which is correct for values only one node ever sets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel

from app.jobs.models import NormalizedJob
from app.matching.models import MatchResult
from app.profile.models import CandidateProfile


class ScoredJob(BaseModel):
    job: NormalizedJob
    match: MatchResult


class JobAutomationState(TypedDict, total=False):
    run_id: str

    candidate_profile: CandidateProfile | None
    search_policy: dict[str, Any]

    enabled_portals: list[str]
    current_portal: str | None

    discovered_jobs: Annotated[list[dict[str, Any]], operator.add]
    normalized_jobs: list[NormalizedJob]
    duplicate_jobs: list[NormalizedJob]

    scored_jobs: list[ScoredJob]
    rejected_jobs: list[ScoredJob]
    application_queue: list[ScoredJob]
    human_review_jobs: list[ScoredJob]

    human_action_required: bool
    human_action_reason: str | None

    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]

    metrics: dict[str, Any]

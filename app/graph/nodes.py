"""LangGraph node functions (Section 4/23).

Each node is a small, mostly-deterministic function: `discover` and `score`
delegate entirely to plain code (mock portals, the Phase 2 matching engine)
rather than an LLM, per Section 2's core principle. The only place this
graph pauses is `policy_guard`, when a job's score falls in the
`human_review` band — Section 19's interrupt framework, demonstrated with a
real (if narrow) reason rather than a stub.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.core.config import get_yaml_config_loader
from app.core.errors import JobAutomationError
from app.core.logging import get_logger
from app.database.session import get_sessionmaker
from app.graph.mock_portals import MOCK_PORTALS
from app.graph.state import JobAutomationState, ScoredJob
from app.guardrails.engine import run_guardrails
from app.guardrails.models import GuardrailContext, GuardrailDecision
from app.jobs.models import NormalizedJob
from app.jobs.parser import normalize_job
from app.matching.models import Recommendation, load_scoring_thresholds, load_scoring_weights
from app.matching.scorer import score_job
from app.matching.title import title_family
from app.portals.registry import build_adapter, resolve_enabled_real_portals
from app.profile import profile_service
from app.profile.models import CandidateProfile

logger = get_logger(__name__)


async def load_candidate_profile_node(state: JobAutomationState) -> dict[str, Any]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        profile = await profile_service.get_profile(session)

    if profile is None:
        return {
            "candidate_profile": None,
            "errors": [{"error": "No candidate profile found — import a resume first."}],
        }
    return {"candidate_profile": profile}


async def load_search_policy_node(state: JobAutomationState) -> dict[str, Any]:
    search_policy = get_yaml_config_loader().load("search")
    portals_config = get_yaml_config_loader().load("portals")

    enabled = search_policy.get("search", {}).get("enabled_portals") or []
    if not enabled:
        real_portals = resolve_enabled_real_portals(portals_config)
        if real_portals:
            # At least one real portal is configured — prefer it over the
            # mock demo portals (every config/portals.yaml section ships
            # with an empty identifier list, so a fresh install never
            # hits this branch unedited).
            enabled = real_portals
        else:
            # Nothing real configured yet; fall back to the local mock
            # portals so the graph has something to demonstrate with.
            enabled = list(MOCK_PORTALS.keys())

    return {"search_policy": search_policy, "enabled_portals": enabled}


async def discover_portal_node(state: JobAutomationState) -> dict[str, Any]:
    portal = state["current_portal"]

    if portal and portal in MOCK_PORTALS:
        try:
            raw_jobs = MOCK_PORTALS[portal](state.get("search_policy", {}))
        except Exception as exc:  # a portal failure must not abort the whole run
            logger.warning("portal_discovery_failed", portal=portal, error=str(exc))
            return {"errors": [{"portal": portal, "error": str(exc)}]}
        for raw in raw_jobs:
            raw["_source"] = portal
        return {"discovered_jobs": raw_jobs}

    adapter = build_adapter(portal) if portal else None
    if adapter is not None:
        try:
            raw_jobs = await adapter.discover_jobs(state.get("search_policy", {}))
        except JobAutomationError as exc:
            # A typed portal/browser/LLM error — captures richer context
            # (url, step, timestamp, ...) than a generic exception can;
            # "error" is kept alongside "message" for backward
            # compatibility with anything reading the plain-Exception shape.
            logger.warning(
                "portal_discovery_failed",
                portal=portal,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return {"errors": [{"error": str(exc), **exc.to_dict(), "portal": portal}]}
        except Exception as exc:  # a portal failure must not abort the whole run
            logger.warning("portal_discovery_failed", portal=portal, error=str(exc))
            return {"errors": [{"portal": portal, "error": str(exc)}]}
        for raw in raw_jobs:
            raw["_source"] = portal
        return {"discovered_jobs": raw_jobs}

    return {"warnings": [f"Unknown or unconfigured portal: {portal}"]}


async def normalize_jobs_node(state: JobAutomationState) -> dict[str, Any]:
    normalized: list[NormalizedJob] = []
    errors: list[dict[str, Any]] = []

    for raw in state.get("discovered_jobs", []):
        source = raw.get("_source", "unknown")
        raw_copy = {k: v for k, v in raw.items() if k != "_source"}
        try:
            normalized.append(normalize_job(raw_copy, source=source))
        except ValueError as exc:
            errors.append({"source": source, "error": str(exc), "raw_title": raw.get("title")})

    result: dict[str, Any] = {"normalized_jobs": normalized}
    if errors:
        result["errors"] = errors
    return result


async def dedupe_jobs_node(state: JobAutomationState) -> dict[str, Any]:
    """Cross-portal duplicate detection (Section 14).

    Groups on (company, title family, location) — the same opportunity
    posted to two different portals collapses to whichever was seen first.
    Runs after normalization (not before, unlike the narrative diagram in
    Section 4) since it needs the title-family canonicalization that
    normalization/matching already provides, per Section 14's own
    "normalized title" matching key.
    """
    seen: dict[tuple[str, str, str], NormalizedJob] = {}
    unique: list[NormalizedJob] = []
    duplicates: list[NormalizedJob] = []

    for job in state.get("normalized_jobs", []):
        family = (title_family(job.title) or job.title).strip().lower()
        key = (job.company.strip().lower(), family, (job.location or "").strip().lower())
        if key in seen:
            duplicates.append(job)
        else:
            seen[key] = job
            unique.append(job)

    return {"normalized_jobs": unique, "duplicate_jobs": duplicates}


async def score_jobs_node(state: JobAutomationState) -> dict[str, Any]:
    profile = state.get("candidate_profile")
    if profile is None:
        return {"scored_jobs": []}

    candidate_skills = list(profile.preferences.skills_primary) + list(
        profile.preferences.skills_secondary
    )
    experience_years = None
    if profile.resume is not None:
        candidate_skills += profile.resume.skills.all_skills()
        experience_years = profile.resume.experience_years.value

    weights = load_scoring_weights()
    thresholds = load_scoring_thresholds()

    scored = [
        ScoredJob(
            job=job,
            match=score_job(
                job,
                preferences=profile.preferences,
                candidate_skills=candidate_skills,
                candidate_experience_years=experience_years,
                weights=weights,
                thresholds=thresholds,
            ),
        )
        for job in state.get("normalized_jobs", [])
    ]
    return {"scored_jobs": scored}


def _with_guardrail_note(
    scored_job: ScoredJob, note: str, recommendation: Recommendation
) -> ScoredJob:
    updated_match = scored_job.match.model_copy(
        update={
            "reason": f"{scored_job.match.reason} | guardrails: {note}",
            "recommendation": recommendation,
        }
    )
    return ScoredJob(job=scored_job.job, match=updated_match)


async def policy_guard_node(state: JobAutomationState) -> dict[str, Any]:
    """Score-based routing (Phase 3), then the deterministic guardrail
    engine (Section 17/Phase 4) has final say on every non-rejected job —
    it can only make a job *more* restricted (queue -> human_review ->
    reject), never less, per Section 23's "supervisor must not bypass or
    override guardrails".
    """
    scored = state.get("scored_jobs", [])
    profile: CandidateProfile | None = state.get("candidate_profile")

    rejected: list[ScoredJob] = [s for s in scored if s.match.recommendation == "reject"]
    human_review: list[ScoredJob] = []
    queue: list[ScoredJob] = []

    for scored_job in scored:
        if scored_job.match.recommendation == "reject":
            continue  # already in `rejected` above

        if profile is None:
            # No profile to evaluate guardrails against — fall back to
            # score-only routing.
            target = human_review if scored_job.match.recommendation == "human_review" else queue
            target.append(scored_job)
            continue

        report = run_guardrails(
            GuardrailContext(job=scored_job.job, match=scored_job.match, profile=profile)
        )
        if report.decision == GuardrailDecision.BLOCK:
            rejected.append(
                _with_guardrail_note(scored_job, "; ".join(report.blocking_reasons), "reject")
            )
        elif report.decision == GuardrailDecision.HUMAN_INPUT_REQUIRED:
            human_review.append(
                _with_guardrail_note(
                    scored_job, "; ".join(report.human_input_reasons), "human_review"
                )
            )
        elif scored_job.match.recommendation == "human_review":
            human_review.append(scored_job)
        else:
            queue.append(scored_job)

    if human_review:
        decision: dict[str, str] = (
            interrupt(
                {
                    "reason": "HUMAN_REVIEW_REQUIRED",
                    "jobs": [
                        {
                            "job_id": s.job.id,
                            "title": s.job.title,
                            "company": s.job.company,
                            "score": s.match.overall_score,
                            "note": s.match.reason,
                        }
                        for s in human_review
                    ],
                }
            )
            or {}
        )
        still_pending: list[ScoredJob] = []
        for scored_job in human_review:
            outcome = decision.get(scored_job.job.id)
            if outcome == "queue":
                queue.append(scored_job)
            elif outcome == "reject":
                rejected.append(scored_job)
            else:
                still_pending.append(scored_job)
        human_review = still_pending

    return {
        "rejected_jobs": rejected,
        "application_queue": queue,
        "human_review_jobs": human_review,
        "human_action_required": bool(human_review),
        "human_action_reason": "HUMAN_REVIEW_REQUIRED" if human_review else None,
    }


async def finalize_node(state: JobAutomationState) -> dict[str, Any]:
    metrics = {
        "discovered": len(state.get("discovered_jobs", [])),
        "duplicates": len(state.get("duplicate_jobs", [])),
        "scored": len(state.get("scored_jobs", [])),
        "rejected": len(state.get("rejected_jobs", [])),
        "queued": len(state.get("application_queue", [])),
        "human_review_pending": len(state.get("human_review_jobs", [])),
    }
    return {"metrics": metrics}

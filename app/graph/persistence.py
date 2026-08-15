"""Dashboard persistence (Section 27, Phase 8).

Phases 3/6 deliberately used only the LangGraph checkpointer for
in-flight run/application state — correct for resuming a single run, but
it leaves nothing to list, filter, or chart once a run finishes. This
module is the write path (called from `service.py`/`apply_service.py`
right after a graph invocation, using the *raw* state dict — before
`_summarize()` strips it down to the small `RunResult`/`ApplicationResult`
the API returns) and the read path the dashboard's new endpoints query.

Deliberately plain SQLAlchemy, not a repository-class abstraction — this
is a handful of straightforward upserts and filtered selects, and adding a
layer of indirection over that wouldn't earn its keep.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.application import ApplicationRecord
from app.database.models.automation_run import AutomationRunRecord
from app.database.models.human_intervention import HumanInterventionRecord
from app.database.models.job import JobRecord
from app.graph.state import ScoredJob
from app.jobs.models import NormalizedJob
from app.matching.models import MatchResult

# --- writes: discovery runs -------------------------------------------------


async def _upsert_job_record(
    session: AsyncSession,
    *,
    run_id: str,
    job: NormalizedJob,
    status: str,
    match: MatchResult | None,
) -> None:
    record = await session.get(JobRecord, job.id)
    if record is None:
        record = JobRecord(id=job.id)
        session.add(record)

    record.run_id = run_id
    record.external_job_id = job.external_job_id
    record.source = job.source
    record.url = job.url
    record.title = job.title
    record.company = job.company
    record.location = job.location
    record.work_mode = job.work_mode
    record.salary_min = job.salary_min
    record.salary_max = job.salary_max
    record.salary_currency = job.salary_currency
    record.description = job.description
    record.industry = job.industry
    record.employment_type = job.employment_type
    record.posted_at = job.posted_at
    record.discovered_at = job.discovered_at
    record.status = status
    record.metadata_json = job.metadata

    if match is not None:
        record.overall_score = match.overall_score
        record.breakdown = match.breakdown.model_dump()
        record.matched_skills = match.matched_skills
        record.missing_skills = match.missing_skills
        record.recommendation = match.recommendation
        record.reason = match.reason


async def persist_run_result(session: AsyncSession, run_id: str, state: dict[str, Any]) -> None:
    interrupts: list[Any] | None = state.get("__interrupt__")
    is_paused = bool(interrupts)
    status = "waiting_human" if is_paused else "completed"

    run = await session.get(AutomationRunRecord, run_id)
    if run is None:
        run = AutomationRunRecord(id=run_id, status=status)
        session.add(run)
    run.status = status
    run.enabled_portals = list(state.get("enabled_portals", []))
    run.metrics = state.get("metrics")
    run.warnings = state.get("warnings", [])
    run.errors = state.get("errors", [])
    if not is_paused and run.completed_at is None:
        run.completed_at = datetime.now(UTC)

    scored_job: ScoredJob
    for scored_job in state.get("application_queue", []):
        await _upsert_job_record(
            session, run_id=run_id, job=scored_job.job, status="queued", match=scored_job.match
        )
    for scored_job in state.get("rejected_jobs", []):
        await _upsert_job_record(
            session, run_id=run_id, job=scored_job.job, status="rejected", match=scored_job.match
        )
    for scored_job in state.get("human_review_jobs", []):
        await _upsert_job_record(
            session,
            run_id=run_id,
            job=scored_job.job,
            status="human_review",
            match=scored_job.match,
        )
    for dup_job in state.get("duplicate_jobs", []):
        await _upsert_job_record(
            session, run_id=run_id, job=dup_job, status="duplicate", match=None
        )

    if interrupts:
        await _upsert_pending_intervention(
            session,
            kind="run",
            ref_id=run_id,
            reason=interrupts[0].value.get("reason", "UNKNOWN"),
            payload=interrupts[0].value,
        )
    else:
        await _resolve_interventions(session, kind="run", ref_id=run_id)

    await session.commit()


# --- writes: applications ---------------------------------------------------


async def create_application_record(
    session: AsyncSession,
    *,
    application_id: str,
    job: NormalizedJob,
    form_page_url: str,
) -> None:
    session.add(
        ApplicationRecord(
            id=application_id,
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            form_page_url=form_page_url,
            status="waiting_human",
        )
    )
    await session.commit()


async def persist_application_result(
    session: AsyncSession, application_id: str, state: dict[str, Any]
) -> None:
    interrupts = state.get("__interrupt__")
    record = await session.get(ApplicationRecord, application_id)
    if record is None:
        # Shouldn't happen (create_application_record runs first), but
        # don't crash the request over a missing dashboard row.
        return

    if interrupts:
        reason = interrupts[0].value.get("reason", "UNKNOWN")
        record.status = "waiting_human"
        record.interrupt_reason = reason
        await _upsert_pending_intervention(
            session,
            kind="application",
            ref_id=application_id,
            reason=reason,
            payload=interrupts[0].value,
        )
    else:
        record.status = state.get("status", "completed")
        record.interrupt_reason = None
        if record.status in ("dry_run_ready", "submitted_mock"):
            record.submitted_at = datetime.now(UTC)
        await _resolve_interventions(session, kind="application", ref_id=application_id)

    await session.commit()


# --- writes: human interventions --------------------------------------------


async def _upsert_pending_intervention(
    session: AsyncSession, *, kind: str, ref_id: str, reason: str, payload: dict[str, Any]
) -> None:
    existing = await session.execute(
        select(HumanInterventionRecord).where(
            HumanInterventionRecord.kind == kind,
            HumanInterventionRecord.ref_id == ref_id,
            HumanInterventionRecord.status == "pending",
        )
    )
    record = existing.scalar_one_or_none()
    if record is None:
        record = HumanInterventionRecord(kind=kind, ref_id=ref_id)
        session.add(record)
    record.reason = reason
    record.payload = payload
    record.status = "pending"
    record.resolved_at = None


async def _resolve_interventions(session: AsyncSession, *, kind: str, ref_id: str) -> None:
    existing = await session.execute(
        select(HumanInterventionRecord).where(
            HumanInterventionRecord.kind == kind,
            HumanInterventionRecord.ref_id == ref_id,
            HumanInterventionRecord.status == "pending",
        )
    )
    for record in existing.scalars():
        record.status = "resolved"
        record.resolved_at = datetime.now(UTC)


# --- reads --------------------------------------------------------------


async def list_jobs(
    session: AsyncSession,
    *,
    status: str | None = None,
    company: str | None = None,
    source: str | None = None,
    run_id: str | None = None,
    min_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JobRecord]:
    query = select(JobRecord).order_by(JobRecord.discovered_at.desc())
    if status:
        query = query.where(JobRecord.status == status)
    if company:
        query = query.where(JobRecord.company.ilike(f"%{company}%"))
    if source:
        query = query.where(JobRecord.source == source)
    if run_id:
        query = query.where(JobRecord.run_id == run_id)
    if min_score is not None:
        query = query.where(JobRecord.overall_score >= min_score)
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_job(session: AsyncSession, job_id: str) -> JobRecord | None:
    return await session.get(JobRecord, job_id)


async def get_application_by_job_id(session: AsyncSession, job_id: str) -> ApplicationRecord | None:
    """Section 50: "before submitting, check existing application" — used
    by `apply_service.start_application` to raise `DuplicateApplicationError`
    rather than silently creating a second application for the same job.
    """
    result = await session.execute(
        select(ApplicationRecord).where(ApplicationRecord.job_id == job_id)
    )
    return result.scalars().first()


async def list_applications(
    session: AsyncSession, *, status: str | None = None, limit: int = 50, offset: int = 0
) -> list[ApplicationRecord]:
    query = select(ApplicationRecord).order_by(ApplicationRecord.created_at.desc())
    if status:
        query = query.where(ApplicationRecord.status == status)
    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_runs(
    session: AsyncSession, *, limit: int = 20, offset: int = 0
) -> list[AutomationRunRecord]:
    query = (
        select(AutomationRunRecord)
        .order_by(AutomationRunRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_human_interventions(
    session: AsyncSession, *, status: str = "pending"
) -> list[HumanInterventionRecord]:
    query = (
        select(HumanInterventionRecord)
        .where(HumanInterventionRecord.status == status)
        .order_by(HumanInterventionRecord.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())

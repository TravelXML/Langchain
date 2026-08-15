"""Run orchestration: start/resume/inspect a graph run (Section 33's /api/runs).

Each call opens its own checkpointer connection (see
``graph.compiled_graph``) rather than holding one open for the process
lifetime — proving the run genuinely resumes from persisted state, not from
anything held in Python memory.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel

from app.database.session import get_sessionmaker
from app.graph import persistence
from app.graph.graph import compiled_graph
from app.graph.state import ScoredJob
from app.notifications.models import NotificationEvent, NotificationKind
from app.notifications.service import notify_all


def _run_config(run_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": run_id}}


class JobSummary(BaseModel):
    job_id: str
    title: str
    company: str
    score: float
    recommendation: str
    reason: str


class RunResult(BaseModel):
    run_id: str
    status: Literal["completed", "waiting_human"]
    metrics: dict[str, int] | None = None
    queued: list[JobSummary] = []
    rejected: list[JobSummary] = []
    duplicates: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    interrupt: dict[str, Any] | None = None


def _job_summary(scored: ScoredJob) -> JobSummary:
    return JobSummary(
        job_id=scored.job.id,
        title=scored.job.title,
        company=scored.job.company,
        score=scored.match.overall_score,
        recommendation=scored.match.recommendation,
        reason=scored.match.reason,
    )


def _summarize(run_id: str, state: dict[str, Any], interrupt: dict[str, Any] | None) -> RunResult:
    if interrupt is not None:
        return RunResult(run_id=run_id, status="waiting_human", interrupt=interrupt)

    return RunResult(
        run_id=run_id,
        status="completed",
        metrics=state.get("metrics"),
        queued=[_job_summary(s) for s in state.get("application_queue", [])],
        rejected=[_job_summary(s) for s in state.get("rejected_jobs", [])],
        duplicates=[j.title for j in state.get("duplicate_jobs", [])],
        warnings=state.get("warnings", []),
        errors=state.get("errors", []),
    )


async def _notify_run_outcome(result: RunResult) -> None:
    if result.status == "waiting_human":
        await notify_all(
            NotificationEvent(
                kind=NotificationKind.HUMAN_INTERVENTION_REQUIRED,
                title="Discovery run needs your review",
                message=f"Run {result.run_id} is waiting on a human decision.",
                metadata={"run_id": result.run_id, "interrupt": result.interrupt},
            )
        )
    elif result.errors:
        await notify_all(
            NotificationEvent(
                kind=NotificationKind.RUN_FAILED,
                title="Discovery run finished with errors",
                message=f"Run {result.run_id} completed with {len(result.errors)} error(s).",
                metadata={"run_id": result.run_id, "errors": result.errors},
            )
        )
    else:
        queued = result.metrics.get("queued", 0) if result.metrics else 0
        await notify_all(
            NotificationEvent(
                kind=NotificationKind.RUN_COMPLETED,
                title="Discovery run completed",
                message=f"Run {result.run_id} completed: {queued} job(s) queued.",
                metadata={"run_id": result.run_id, "metrics": result.metrics},
            )
        )


async def start_run() -> RunResult:
    run_id = str(uuid.uuid4())
    config = _run_config(run_id)

    async with compiled_graph() as graph:
        result = await graph.ainvoke({"run_id": run_id}, config=config)

    async with get_sessionmaker()() as session:
        await persistence.persist_run_result(session, run_id, result)

    interrupts = result.get("__interrupt__")
    interrupt_payload = interrupts[0].value if interrupts else None
    summary = _summarize(run_id, result, interrupt_payload)
    await _notify_run_outcome(summary)
    return summary


async def resume_run(run_id: str, decisions: dict[str, str]) -> RunResult | None:
    config = _run_config(run_id)

    async with compiled_graph() as graph:
        snapshot = await graph.aget_state(config)
        if not snapshot.values:
            return None

        result = await graph.ainvoke(Command(resume=decisions), config=config)

    async with get_sessionmaker()() as session:
        await persistence.persist_run_result(session, run_id, result)

    interrupts = result.get("__interrupt__")
    interrupt_payload = interrupts[0].value if interrupts else None
    summary = _summarize(run_id, result, interrupt_payload)
    await _notify_run_outcome(summary)
    return summary


async def get_run_state(run_id: str) -> RunResult | None:
    config = _run_config(run_id)

    async with compiled_graph() as graph:
        snapshot = await graph.aget_state(config)

    if not snapshot.values:
        return None

    if snapshot.next:
        # Paused: the pending interrupt payload lives on the queued task.
        interrupt_payload = None
        for task in snapshot.tasks:
            if task.interrupts:
                interrupt_payload = task.interrupts[0].value
                break
        return _summarize(run_id, snapshot.values, interrupt_payload)

    return _summarize(run_id, snapshot.values, None)

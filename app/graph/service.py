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

from app.graph.graph import compiled_graph
from app.graph.state import ScoredJob


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


async def start_run() -> RunResult:
    run_id = str(uuid.uuid4())
    config = _run_config(run_id)

    async with compiled_graph() as graph:
        result = await graph.ainvoke({"run_id": run_id}, config=config)

    interrupts = result.get("__interrupt__")
    interrupt_payload = interrupts[0].value if interrupts else None
    return _summarize(run_id, result, interrupt_payload)


async def resume_run(run_id: str, decisions: dict[str, str]) -> RunResult | None:
    config = _run_config(run_id)

    async with compiled_graph() as graph:
        snapshot = await graph.aget_state(config)
        if not snapshot.values:
            return None

        result = await graph.ainvoke(Command(resume=decisions), config=config)

    interrupts = result.get("__interrupt__")
    interrupt_payload = interrupts[0].value if interrupts else None
    return _summarize(run_id, result, interrupt_payload)


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

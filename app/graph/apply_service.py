"""Application run orchestration (Section 33's future /api/applications,
Phase 6 subset): start/resume/inspect one apply-graph run.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel

from app.database.session import get_sessionmaker
from app.graph.apply_graph import compiled_apply_graph
from app.jobs.models import NormalizedJob
from app.profile import profile_service


class ApplicationResult(BaseModel):
    application_id: str
    status: Literal["completed", "waiting_human"]
    application_status: str | None = None  # rejected_by_human / dry_run_ready / submitted_mock
    interrupt: dict[str, Any] | None = None
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []


def _run_config(application_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": application_id}}


def _summarize(
    application_id: str, state: dict[str, Any], interrupt: dict[str, Any] | None
) -> ApplicationResult:
    if interrupt is not None:
        return ApplicationResult(
            application_id=application_id, status="waiting_human", interrupt=interrupt
        )
    return ApplicationResult(
        application_id=application_id,
        status="completed",
        application_status=state.get("status"),
        warnings=state.get("warnings", []),
        errors=state.get("errors", []),
    )


async def start_application(
    job: NormalizedJob, *, form_page_url: str, challenge_page_urls: list[str] | None = None
) -> ApplicationResult | None:
    async with get_sessionmaker()() as session:
        profile = await profile_service.get_profile(session)
    if profile is None:
        return None

    application_id = str(uuid.uuid4())
    initial_state = {
        "application_id": application_id,
        "job": job,
        "candidate_profile": profile,
        "form_page_url": form_page_url,
        "challenge_page_urls": challenge_page_urls or [],
    }

    async with compiled_apply_graph() as graph:
        result = await graph.ainvoke(initial_state, config=_run_config(application_id))

    interrupts = result.get("__interrupt__")
    interrupt_payload = interrupts[0].value if interrupts else None
    return _summarize(application_id, result, interrupt_payload)


async def resume_application(
    application_id: str, payload: dict[str, Any]
) -> ApplicationResult | None:
    config = _run_config(application_id)
    async with compiled_apply_graph() as graph:
        snapshot = await graph.aget_state(config)
        if not snapshot.values:
            return None
        result = await graph.ainvoke(Command(resume=payload), config=config)

    interrupts = result.get("__interrupt__")
    interrupt_payload = interrupts[0].value if interrupts else None
    return _summarize(application_id, result, interrupt_payload)


async def get_application_state(application_id: str) -> ApplicationResult | None:
    config = _run_config(application_id)
    async with compiled_apply_graph() as graph:
        snapshot = await graph.aget_state(config)

    if not snapshot.values:
        return None

    if snapshot.next:
        interrupt_payload = None
        for task in snapshot.tasks:
            if task.interrupts:
                interrupt_payload = task.interrupts[0].value
                break
        return _summarize(application_id, snapshot.values, interrupt_payload)

    return _summarize(application_id, snapshot.values, None)

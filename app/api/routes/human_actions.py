"""Unified human-review queue spanning both interrupt sources (Section 33) —
Phase 3's discovery-run interrupts and Phase 6's apply-graph interrupts.
Resolving here dispatches to whichever graph's own resume function actually
owns the interrupt; this endpoint is a queue view over both, not a third
interrupt mechanism.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.human_intervention import HumanInterventionRecord
from app.database.session import get_session
from app.graph import apply_service, persistence
from app.graph import service as run_service
from app.graph.apply_service import ApplicationResult
from app.graph.service import RunResult

router = APIRouter(prefix="/api/human-actions", tags=["human-actions"])


class HumanActionOut(BaseModel):
    id: str
    kind: str
    ref_id: str
    reason: str
    payload: dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveHumanActionRequest(BaseModel):
    decisions: dict[str, str] | None = None  # kind="run"
    payload: dict[str, Any] | None = None  # kind="application"


@router.get("", response_model=list[HumanActionOut])
async def list_human_actions(session: AsyncSession = Depends(get_session)) -> list[HumanActionOut]:
    records = await persistence.list_human_interventions(session, status="pending")
    return [HumanActionOut.model_validate(r) for r in records]


@router.post("/{intervention_id}/resolve")
async def resolve_human_action(
    intervention_id: str,
    body: ResolveHumanActionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    record = await session.get(HumanInterventionRecord, intervention_id)
    if record is None or record.status != "pending":
        raise HTTPException(status_code=404, detail="Pending human action not found")

    result: RunResult | ApplicationResult | None
    if record.kind == "run":
        if body.decisions is None:
            raise HTTPException(
                status_code=422, detail="'decisions' is required to resolve a run intervention"
            )
        result = await run_service.resume_run(record.ref_id, body.decisions)
    elif record.kind == "application":
        if body.payload is None:
            raise HTTPException(
                status_code=422,
                detail="'payload' is required to resolve an application intervention",
            )
        result = await apply_service.resume_application(record.ref_id, body.payload)
    else:
        raise HTTPException(status_code=500, detail=f"unknown intervention kind: {record.kind}")

    if result is None:
        raise HTTPException(status_code=404, detail=f"{record.kind} {record.ref_id} not found")
    return result.model_dump()

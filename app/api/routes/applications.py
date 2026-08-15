from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DuplicateApplicationError
from app.database.session import get_session
from app.graph import apply_service, persistence
from app.graph.apply_service import ApplicationResult
from app.jobs.models import NormalizedJob

router = APIRouter(prefix="/api/applications", tags=["applications"])


class StartApplicationRequest(BaseModel):
    job: NormalizedJob
    form_page_url: str
    challenge_page_urls: list[str] = []
    # Section 48's hybrid approval mode: the discovery graph's
    # MatchResult.overall_score for this job, if the caller has one.
    # Optional — hybrid mode never auto-approves without it.
    match_score: float | None = None


class ResumeApplicationRequest(BaseModel):
    payload: dict[str, Any]


class ApplicationListItem(BaseModel):
    id: str
    job_id: str | None
    job_title: str
    company: str
    status: str
    interrupt_reason: str | None
    submitted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ApplicationListItem])
async def list_applications(
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationListItem]:
    records = await persistence.list_applications(
        session, status=status, limit=limit, offset=offset
    )
    return [ApplicationListItem.model_validate(r) for r in records]


@router.post("", response_model=ApplicationResult)
async def create_application(body: StartApplicationRequest) -> ApplicationResult:
    try:
        result = await apply_service.start_application(
            body.job,
            form_page_url=body.form_page_url,
            challenge_page_urls=body.challenge_page_urls,
            match_score=body.match_score,
        )
    except DuplicateApplicationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(
            status_code=409, detail="No candidate profile found — import a resume first."
        )
    return result


@router.get("/{application_id}", response_model=ApplicationResult)
async def get_application(application_id: str) -> ApplicationResult:
    result = await apply_service.get_application_state(application_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.post("/{application_id}/resume", response_model=ApplicationResult)
async def resume_application(
    application_id: str, body: ResumeApplicationRequest
) -> ApplicationResult:
    result = await apply_service.resume_application(application_id, body.payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return result

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph import apply_service
from app.graph.apply_service import ApplicationResult
from app.jobs.models import NormalizedJob

router = APIRouter(prefix="/api/applications", tags=["applications"])


class StartApplicationRequest(BaseModel):
    job: NormalizedJob
    form_page_url: str
    challenge_page_urls: list[str] = []


class ResumeApplicationRequest(BaseModel):
    payload: dict[str, Any]


@router.post("", response_model=ApplicationResult)
async def create_application(body: StartApplicationRequest) -> ApplicationResult:
    result = await apply_service.start_application(
        body.job, form_page_url=body.form_page_url, challenge_page_urls=body.challenge_page_urls
    )
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

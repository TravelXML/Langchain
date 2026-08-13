from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import get_session
from app.profile import profile_service
from app.profile.loader import PdfExtractionError
from app.profile.models import CandidatePreferences, CandidateProfile

router = APIRouter(prefix="/api/profile", tags=["profile"])
logger = get_logger(__name__)


async def _save_upload(upload: UploadFile, subdir: str) -> Path:
    if upload.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Expected a PDF file for '{upload.filename}', got {upload.content_type}",
        )

    target_dir = get_settings().upload_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{Path(upload.filename or 'upload.pdf').name}"
    target_path = target_dir / safe_name

    content = await upload.read()
    target_path.write_bytes(content)
    return target_path


@router.get("", response_model=CandidateProfile)
async def get_profile(session: AsyncSession = Depends(get_session)) -> CandidateProfile:
    profile = await profile_service.get_profile(session)
    if profile is None:
        raise HTTPException(status_code=404, detail="No candidate profile has been imported yet")
    return profile


@router.post("/import", response_model=CandidateProfile)
async def import_profile(
    resume: UploadFile,
    cover_letter: UploadFile | None = None,
    session: AsyncSession = Depends(get_session),
) -> CandidateProfile:
    resume_path = await _save_upload(resume, "resumes")
    cover_letter_path = (
        await _save_upload(cover_letter, "cover_letters") if cover_letter is not None else None
    )

    try:
        return await profile_service.import_profile(
            session, resume_path=resume_path, cover_letter_path=cover_letter_path
        )
    except PdfExtractionError as exc:
        logger.warning("profile_import_failed", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("", response_model=CandidateProfile)
async def update_preferences(
    preferences: CandidatePreferences,
    session: AsyncSession = Depends(get_session),
) -> CandidateProfile:
    return await profile_service.update_preferences(session, preferences)

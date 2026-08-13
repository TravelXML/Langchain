"""Top-level candidate profile orchestration: DB persistence + assembly of
parsed resume + cover letter + config-driven preferences into one
``CandidateProfile``.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_yaml_config_loader
from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.profile.cover_letter_service import extract_cover_letter_text
from app.profile.models import CandidatePreferences, CandidateProfile, ResumeExtraction
from app.profile.resume_service import build_resume_extraction


def load_preferences_from_config() -> CandidatePreferences:
    raw = get_yaml_config_loader().load("candidate")
    return CandidatePreferences.from_yaml(raw)


async def get_profile(session: AsyncSession) -> CandidateProfile | None:
    record = await session.get(CandidateProfileRecord, DEFAULT_PROFILE_ID)
    if record is None:
        return None
    return _record_to_model(record)


async def import_profile(
    session: AsyncSession,
    *,
    resume_path: Path,
    cover_letter_path: Path | None = None,
) -> CandidateProfile:
    preferences = load_preferences_from_config()
    resume = build_resume_extraction(
        resume_path,
        primary_skills=preferences.skills_primary,
        secondary_skills=preferences.skills_secondary,
    )

    cover_letter_text: str | None = None
    cover_letter_source_file: str | None = None
    if cover_letter_path is not None:
        cover_letter_text = extract_cover_letter_text(cover_letter_path)
        cover_letter_source_file = cover_letter_path.name

    record = await session.get(CandidateProfileRecord, DEFAULT_PROFILE_ID)
    if record is None:
        record = CandidateProfileRecord(id=DEFAULT_PROFILE_ID)
        session.add(record)

    record.resume = resume.model_dump(mode="json")
    record.cover_letter_text = cover_letter_text
    record.cover_letter_source_file = cover_letter_source_file
    record.preferences = preferences.model_dump(mode="json")

    await session.commit()
    await session.refresh(record)
    return _record_to_model(record)


async def update_preferences(
    session: AsyncSession, preferences: CandidatePreferences
) -> CandidateProfile:
    record = await session.get(CandidateProfileRecord, DEFAULT_PROFILE_ID)
    if record is None:
        record = CandidateProfileRecord(
            id=DEFAULT_PROFILE_ID, preferences=preferences.model_dump(mode="json")
        )
        session.add(record)
    else:
        record.preferences = preferences.model_dump(mode="json")

    await session.commit()
    await session.refresh(record)
    return _record_to_model(record)


def _record_to_model(record: CandidateProfileRecord) -> CandidateProfile:
    return CandidateProfile(
        id=record.id,
        resume=ResumeExtraction.model_validate(record.resume) if record.resume else None,
        cover_letter_text=record.cover_letter_text,
        cover_letter_source_file=record.cover_letter_source_file,
        preferences=CandidatePreferences.model_validate(record.preferences),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

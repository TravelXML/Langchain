"""Builds a structured ResumeExtraction from a resume PDF on disk."""

from __future__ import annotations

from pathlib import Path

from app.profile.loader import extract_text_from_pdf
from app.profile.models import ResumeExtraction
from app.profile.parser import parse_resume_text


def build_resume_extraction(
    path: Path,
    *,
    primary_skills: list[str] | None = None,
    secondary_skills: list[str] | None = None,
) -> ResumeExtraction:
    text = extract_text_from_pdf(path)
    return parse_resume_text(
        text,
        source_file=path.name,
        primary_skills=primary_skills,
        secondary_skills=secondary_skills,
    )

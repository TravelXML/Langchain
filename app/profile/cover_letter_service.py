"""Cover letter text extraction.

Phase 1 only extracts and stores the candidate's existing cover letter text.
Adaptation/generation of new cover letters per job is Phase 22 — deferred
until the LLM integration (Phase 6) exists to drive it.
"""

from __future__ import annotations

from pathlib import Path

from app.profile.loader import extract_text_from_pdf


def extract_cover_letter_text(path: Path) -> str:
    return extract_text_from_pdf(path)

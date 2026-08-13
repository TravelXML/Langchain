from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin

# Local-first, single-candidate system: exactly one profile row exists,
# addressed by this fixed id rather than a generated one.
DEFAULT_PROFILE_ID = "default"


class CandidateProfileRecord(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=DEFAULT_PROFILE_ID)
    resume: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_source_file: Mapped[str | None] = mapped_column(String, nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

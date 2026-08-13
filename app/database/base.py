"""Declarative base and shared mixins for ORM models.

Actual tables (jobs, applications, ...) are introduced in later phases via
Alembic migrations under ``migrations/`` — this module only establishes the
shared foundation so those models have a consistent base to inherit from.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """created_at / updated_at columns, per Section 27 of the spec."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


def generate_uuid() -> str:
    return str(uuid.uuid4())

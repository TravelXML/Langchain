"""Notification event model (Section 35).

A single shape every provider consumes — providers format it however
suits their channel (structured log line, JSON POST body, email body,
desktop toast text); nothing here is channel-specific.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NotificationKind(StrEnum):
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    HUMAN_INTERVENTION_REQUIRED = "human_intervention_required"
    APPLICATION_SUBMITTED = "application_submitted"
    APPLICATION_FAILED = "application_failed"
    DAILY_SUMMARY = "daily_summary"


class NotificationEvent(BaseModel):
    kind: NotificationKind
    title: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

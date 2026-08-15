"""Notification provider abstraction (Section 35)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.notifications.models import NotificationEvent


class NotificationProvider(ABC):
    @abstractmethod
    async def notify(self, event: NotificationEvent) -> None: ...

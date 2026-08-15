"""Console notification provider — always safe, zero setup, the default
(Section 2/Section 35: a fresh install must work with no external
service configured).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.notifications.base import NotificationProvider
from app.notifications.models import NotificationEvent

logger = get_logger(__name__)


class ConsoleNotificationProvider(NotificationProvider):
    async def notify(self, event: NotificationEvent) -> None:
        logger.info(
            "notification",
            kind=event.kind.value,
            title=event.title,
            message=event.message,
            metadata=event.metadata,
        )

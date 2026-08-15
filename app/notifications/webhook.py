"""Webhook notification provider — POSTs the event as JSON to a
configured URL. No retry/queueing: a failed delivery is logged by the
caller (`NotificationService.notify_all`) and dropped, since a
notification is best-effort, not a durable message the rest of the
system depends on.
"""

from __future__ import annotations

import httpx

from app.notifications.base import NotificationProvider
from app.notifications.models import NotificationEvent


class WebhookNotificationProvider(NotificationProvider):
    def __init__(self, url: str, timeout_seconds: float = 10.0) -> None:
        self._url = url
        self._timeout = timeout_seconds

    async def notify(self, event: NotificationEvent) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            await client.post(self._url, json=event.model_dump(mode="json"))

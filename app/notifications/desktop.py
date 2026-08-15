"""Desktop notification provider — shells out to `notify-send` (the
standard Linux desktop-notification CLI, part of libnotify) rather than
adding a cross-platform GUI-notification dependency for a single, purely
optional channel. No-ops (with a one-time logged warning) wherever
`notify-send` isn't on PATH — most CI runners and non-Linux-desktop
machines — since a missing desktop notifier is never a reason to fail a
run.
"""

from __future__ import annotations

import asyncio
import shutil

from app.core.logging import get_logger
from app.notifications.base import NotificationProvider
from app.notifications.models import NotificationEvent

logger = get_logger(__name__)


class DesktopNotificationProvider(NotificationProvider):
    def __init__(self) -> None:
        self._binary = shutil.which("notify-send")
        if self._binary is None:
            logger.warning("desktop_notifications_unavailable", reason="notify-send not on PATH")

    async def notify(self, event: NotificationEvent) -> None:
        if self._binary is None:
            return
        proc = await asyncio.create_subprocess_exec(self._binary, event.title, event.message)
        await proc.wait()

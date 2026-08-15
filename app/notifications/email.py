"""Email notification provider — plain SMTP via the stdlib, no extra
dependency. `smtplib` is synchronous, so the send runs in a thread
(`asyncio.to_thread`) rather than blocking the event loop.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.notifications.base import NotificationProvider
from app.notifications.models import NotificationEvent


class EmailNotificationProvider(NotificationProvider):
    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_address: str,
        to_address: str,
        use_tls: bool = True,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username
        self._smtp_password = smtp_password
        self._from_address = from_address
        self._to_address = to_address
        self._use_tls = use_tls

    def _send_sync(self, event: NotificationEvent) -> None:
        msg = EmailMessage()
        msg["Subject"] = event.title
        msg["From"] = self._from_address
        msg["To"] = self._to_address
        msg.set_content(event.message)

        with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._smtp_username:
                smtp.login(self._smtp_username, self._smtp_password)
            smtp.send_message(msg)

    async def notify(self, event: NotificationEvent) -> None:
        await asyncio.to_thread(self._send_sync, event)

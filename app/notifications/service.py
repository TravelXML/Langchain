"""Builds the active provider set from `config/notifications.yaml` and
fans a single event out to all of them (Section 35).

Providers are rebuilt from config on every `notify_all` call rather than
cached — construction is cheap (no connection is opened until `notify()`
actually runs), and this way an edit made through `PUT /api/settings`
takes effect on the very next notification with no reload step, matching
every other config-editable behavior in this app.
"""

from __future__ import annotations

from app.core.config import get_yaml_config_loader
from app.core.logging import get_logger
from app.notifications.base import NotificationProvider
from app.notifications.console import ConsoleNotificationProvider
from app.notifications.desktop import DesktopNotificationProvider
from app.notifications.email import EmailNotificationProvider
from app.notifications.models import NotificationEvent
from app.notifications.webhook import WebhookNotificationProvider

logger = get_logger(__name__)


def _build_providers() -> list[NotificationProvider]:
    config = get_yaml_config_loader().load("notifications")
    providers_config = config.get("notifications", {}).get("providers", {})
    providers: list[NotificationProvider] = []

    console_config = providers_config.get("console", {})
    if console_config.get("enabled", True):
        providers.append(ConsoleNotificationProvider())

    webhook_config = providers_config.get("webhook", {})
    if webhook_config.get("enabled", False) and webhook_config.get("url"):
        providers.append(WebhookNotificationProvider(url=webhook_config["url"]))

    email_config = providers_config.get("email", {})
    if email_config.get("enabled", False):
        providers.append(
            EmailNotificationProvider(
                smtp_host=email_config.get("smtp_host", ""),
                smtp_port=int(email_config.get("smtp_port", 587)),
                smtp_username=email_config.get("smtp_username", ""),
                smtp_password=email_config.get("smtp_password", ""),
                from_address=email_config.get("from_address", ""),
                to_address=email_config.get("to_address", ""),
                use_tls=email_config.get("use_tls", True),
            )
        )

    desktop_config = providers_config.get("desktop", {})
    if desktop_config.get("enabled", False):
        providers.append(DesktopNotificationProvider())

    return providers


async def notify_all(event: NotificationEvent) -> None:
    for provider in _build_providers():
        try:
            await provider.notify(event)
        except Exception as exc:  # one channel failing must never break another
            logger.warning(
                "notification_provider_failed",
                provider=type(provider).__name__,
                kind=event.kind.value,
                error=str(exc),
            )

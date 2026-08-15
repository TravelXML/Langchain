from __future__ import annotations

import smtplib

import httpx
import pytest

from app.notifications.console import ConsoleNotificationProvider
from app.notifications.desktop import DesktopNotificationProvider
from app.notifications.email import EmailNotificationProvider
from app.notifications.models import NotificationEvent, NotificationKind
from app.notifications.service import _build_providers, notify_all
from app.notifications.webhook import WebhookNotificationProvider


def _event(**overrides: object) -> NotificationEvent:
    defaults: dict[str, object] = dict(
        kind=NotificationKind.RUN_COMPLETED, title="Run completed", message="details"
    )
    defaults.update(overrides)
    return NotificationEvent(**defaults)  # type: ignore[arg-type]


async def test_console_provider_never_raises():
    await ConsoleNotificationProvider().notify(_event())


async def test_webhook_provider_posts_event_json(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_post(self, url, json=None, **kwargs):  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = WebhookNotificationProvider(url="https://example.com/hook")
    event = _event(kind=NotificationKind.APPLICATION_SUBMITTED, message="hi")
    await provider.notify(event)

    assert captured["url"] == "https://example.com/hook"
    assert captured["json"]["kind"] == "application_submitted"  # type: ignore[index]
    assert captured["json"]["message"] == "hi"  # type: ignore[index]


async def test_email_provider_sends_via_smtp(monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, msg):
            sent_messages.append(msg)

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    provider = EmailNotificationProvider(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="pass",
        from_address="bot@example.com",
        to_address="me@example.com",
    )
    await provider.notify(_event(title="Subject line", message="Body text"))

    assert len(sent_messages) == 1
    assert sent_messages[0]["Subject"] == "Subject line"
    assert sent_messages[0]["To"] == "me@example.com"


async def test_desktop_provider_noops_when_notify_send_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)
    provider = DesktopNotificationProvider()
    await provider.notify(_event())  # must not raise


async def test_build_providers_console_enabled_by_default():
    providers = _build_providers()
    assert any(isinstance(p, ConsoleNotificationProvider) for p in providers)
    assert not any(isinstance(p, WebhookNotificationProvider) for p in providers)


async def test_notify_all_isolates_a_failing_provider(monkeypatch):
    calls: list[str] = []

    class FailingProvider:
        async def notify(self, event):
            calls.append("failing")
            raise RuntimeError("boom")

    class OkProvider:
        async def notify(self, event):
            calls.append("ok")

    monkeypatch.setattr(
        "app.notifications.service._build_providers", lambda: [FailingProvider(), OkProvider()]
    )

    await notify_all(_event())

    assert calls == ["failing", "ok"]


@pytest.mark.parametrize("kind", list(NotificationKind))
def test_notification_kind_values_are_stable_strings(kind: NotificationKind):
    # These strings are the wire format sent to webhooks — pin them so a
    # refactor can't silently rename an event kind out from under an
    # already-configured webhook consumer.
    assert kind.value == kind.value.lower()

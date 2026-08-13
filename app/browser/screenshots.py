"""Failure artifacts: screenshot + HTML snapshot + console logs (Section 11).

``attach_console_logger`` returns a list that fills in as the page runs;
pass the same list to ``capture_failure_artifacts`` on error so the report
includes everything logged up to the failure, not just a fresh capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Page

from app.core.config import get_settings


@dataclass
class FailureArtifacts:
    screenshot_path: Path
    html_path: Path
    console_logs: list[str]


def attach_console_logger(page: Page) -> list[str]:
    logs: list[str] = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
    return logs


async def capture_failure_artifacts(
    page: Page, name: str, console_logs: list[str] | None = None
) -> FailureArtifacts:
    settings = get_settings()
    settings.browser_artifacts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    base = settings.browser_artifacts_dir / f"{timestamp}_{name}"
    screenshot_path = base.with_suffix(".png")
    html_path = base.with_suffix(".html")

    await page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(await page.content(), encoding="utf-8")

    return FailureArtifacts(
        screenshot_path=screenshot_path, html_path=html_path, console_logs=console_logs or []
    )

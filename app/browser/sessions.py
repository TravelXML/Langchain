"""Per-portal persistent browser sessions (Section 11).

Cookies/local storage are saved to disk on context close and reloaded on
the next run — logging into a portal shouldn't mean logging in again next
time. Each portal gets its own context (and thus its own storage file), so
sessions never leak between portals.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import Browser, BrowserContext

from app.core.config import get_settings


def _storage_state_path(portal: str) -> Path:
    settings = get_settings()
    settings.browser_sessions_dir.mkdir(parents=True, exist_ok=True)
    return settings.browser_sessions_dir / f"{portal}.json"


@asynccontextmanager
async def portal_context(browser: Browser, portal: str) -> AsyncIterator[BrowserContext]:
    state_path = _storage_state_path(portal)
    storage_state = str(state_path) if state_path.exists() else None

    context = await browser.new_context(storage_state=storage_state)
    context.set_default_timeout(get_settings().browser_default_timeout_ms)
    try:
        yield context
    finally:
        await context.storage_state(path=str(state_path))
        await context.close()

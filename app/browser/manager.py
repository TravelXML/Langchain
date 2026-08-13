"""Browser process lifecycle (Section 11).

Headless/headed is configurable (``BROWSER_HEADLESS``) — never hardcoded —
and cleanup is guaranteed via the context manager even on error.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import Browser, async_playwright

from app.core.config import get_settings


@asynccontextmanager
async def launch_browser() -> AsyncIterator[Browser]:
    settings = get_settings()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=settings.browser_headless)
        try:
            yield browser
        finally:
            await browser.close()

from __future__ import annotations

from pathlib import Path

import pytest

from app.browser.manager import launch_browser

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "html"


def fixture_url(name: str) -> str:
    path = _FIXTURES_DIR / name
    assert path.exists(), f"missing HTML fixture: {path}"
    return f"file://{path}"


@pytest.fixture
async def page():
    async with launch_browser() as browser:
        context = await browser.new_context()
        pg = await context.new_page()
        try:
            yield pg
        finally:
            await context.close()

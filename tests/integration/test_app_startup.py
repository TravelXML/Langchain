"""Proves the app's lifespan doesn't crash when Ollama is unavailable —
using the *real*, unmocked LLM health check against whatever
OLLAMA_BASE_URL/OLLAMA_MODEL this test environment actually has (no
Ollama is installed in this project's development environment, so this
genuinely exercises the "LLM unavailable" path for real, not via a
mock — Section 36: "DO NOT crash entire application").
"""

from __future__ import annotations

from app.main import create_app, lifespan


async def test_lifespan_does_not_crash_without_ollama():
    app = create_app()
    async with lifespan(app):
        pass

"""Ollama provider — talks to a local Ollama instance's REST API
(`/api/tags`, `/api/generate`), no cloud dependency, no API key.

Not live-verified against a real running Ollama instance in this
codebase's development session (none was installed) — every test in
`tests/unit/test_llm_ollama.py` mocks the HTTP layer. Section 36's
startup health check (`app/llm/health.py`) is what actually proves this
works against whatever Ollama instance a real deployment points at; a
fresh install with no Ollama running degrades gracefully rather than
crashing (see that module).
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.errors import LLMUnavailableError, LLMValidationError

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, *, timeout_seconds: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"could not reach Ollama at {self._base_url}: {exc}") from exc

        data: dict[str, Any] = response.json()
        return [m["name"] for m in data.get("models", []) if "name" in m]

    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        schema: type[T] | None = None,
    ) -> str | T:
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if system is not None:
            payload["system"] = system
        if schema is not None:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/generate", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama request failed: {exc}") from exc

        data: dict[str, Any] = response.json()
        text: str = data.get("response", "")

        if schema is None:
            return text

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMValidationError(f"model did not return valid JSON: {exc}") from exc

        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise LLMValidationError(
                f"model output did not match {schema.__name__}: {exc}"
            ) from exc

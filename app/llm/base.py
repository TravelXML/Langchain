"""LLM provider abstraction (Section 36). `app/llm/ollama.py` is the only
implementation today; the interface exists so a fallback (OpenAI-
compatible, `config/llm.yaml`'s `fallback` section) or a different local
runtime can be added without touching any caller.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    @abstractmethod
    async def list_models(self) -> list[str]:
        """Model names currently available to this provider."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        schema: type[T] | None = None,
    ) -> str | T:
        """Run one completion. With `schema`, the provider requests
        structured/JSON output and returns a validated instance of
        `schema` — never a dict, never unvalidated text — raising
        `LLMValidationError` (never a bare `json.JSONDecodeError` or
        pydantic `ValidationError`) if the model's output doesn't
        validate. Without `schema`, returns the raw completion text.
        Raises `LLMUnavailableError` if the provider can't be reached at
        all.
        """

"""Embedding provider abstraction (Section 38) — kept deliberately
separate from `LLMProvider` (Section 36's text-generation interface)
since embeddings are a different capability with a different API shape.

Intended consumers (skill similarity, job-title similarity, job-
description similarity, duplicate similarity, resume selection) all
live in `app/matching/` today via `app/matching/semantic.py`'s
deterministic token-overlap fallback — swapping that fallback for a
real `EmbeddingProvider` requires threading an async call through
`app/matching/title.py`'s currently-synchronous scoring path, a change
deliberately left for when it's actually needed rather than bundled into
this pass (see the README's "Notes for contributors").

Caching is in-process only (a plain dict keyed by a content hash) — lost
on restart, which is an accepted limitation for a first pass ("cache
embeddings, never regenerate unchanged embeddings unnecessarily" is
satisfied within a process lifetime; a persistent cache is future work,
not required by anything that calls this yet).
"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

import httpx

from app.core.logging import get_logger
from app.llm.errors import LLMUnavailableError

logger = get_logger(__name__)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    async def similarity(self, a: str, b: str) -> float:
        vec_a, vec_b = await self.embed(a), await self.embed(b)
        return cosine_similarity(vec_a, vec_b)


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str, *, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._cache: dict[str, list[float]] = {}

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(f"{self._model}:{text}".encode()).hexdigest()

    async def embed(self, text: str) -> list[float]:
        cache_key = self._cache_key(text)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Ollama embeddings request failed: {exc}") from exc

        data = response.json()
        embedding: list[float] = data.get("embedding", [])
        self._cache[cache_key] = embedding
        return embedding

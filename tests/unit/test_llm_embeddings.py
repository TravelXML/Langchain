"""OllamaEmbeddingProvider tests — mocked HTTP only, same caveat as
test_llm_ollama.py: no real Ollama/embedding model was available in this
development session.
"""

from __future__ import annotations

import httpx
import pytest

from app.llm.embeddings import OllamaEmbeddingProvider, cosine_similarity
from app.llm.errors import LLMUnavailableError


def _response(json_body, status_code=200) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost:11434/api/embeddings")
    return httpx.Response(status_code, json=json_body, request=request)


def test_cosine_similarity_identical_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_empty_vector_returns_zero():
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0], []) == 0.0


def test_cosine_similarity_mismatched_length_returns_zero():
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_cosine_similarity_zero_vector_returns_zero():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


async def test_embed_calls_ollama_and_returns_vector(monkeypatch):
    calls = []

    async def fake_post(self, url, json=None, **kwargs):
        calls.append((url, json))
        return _response({"embedding": [0.1, 0.2, 0.3]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
    embedding = await provider.embed("hello world")

    assert embedding == [0.1, 0.2, 0.3]
    assert len(calls) == 1
    assert calls[0][1]["model"] == "nomic-embed-text"
    assert calls[0][1]["prompt"] == "hello world"


async def test_embed_caches_repeated_calls(monkeypatch):
    call_count = 0

    async def fake_post(self, url, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        return _response({"embedding": [0.5, 0.5]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
    await provider.embed("same text")
    await provider.embed("same text")

    assert call_count == 1


async def test_embed_cache_is_keyed_by_model_and_text(monkeypatch):
    async def fake_post(self, url, json=None, **kwargs):
        return _response({"embedding": [1.0] if json["model"] == "model-a" else [2.0]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider_a = OllamaEmbeddingProvider("http://localhost:11434", "model-a")
    provider_b = OllamaEmbeddingProvider("http://localhost:11434", "model-b")

    assert await provider_a.embed("text") == [1.0]
    assert await provider_b.embed("text") == [2.0]


async def test_embed_unreachable_raises_llm_unavailable(monkeypatch):
    async def fake_post(self, url, json=None, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
    with pytest.raises(LLMUnavailableError):
        await provider.embed("hello")


async def test_similarity_computes_cosine_between_two_texts(monkeypatch):
    async def fake_post(self, url, json=None, **kwargs):
        vector = [1.0, 0.0] if json["prompt"] == "a" else [0.0, 1.0]
        return _response({"embedding": vector})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    provider = OllamaEmbeddingProvider("http://localhost:11434", "nomic-embed-text")
    result = await provider.similarity("a", "b")
    assert result == pytest.approx(0.0)

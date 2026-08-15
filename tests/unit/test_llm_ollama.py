"""OllamaProvider tests — mocked HTTP only. No real Ollama instance was
available in this development session (see README's "Local LLM setup"),
so these tests prove the provider's contract (request shape, JSON
parsing, schema validation, error mapping) against a fake server rather
than a real model's behavior.
"""

from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from app.llm.errors import LLMUnavailableError, LLMValidationError
from app.llm.ollama import OllamaProvider


class _Probe(BaseModel):
    ok: bool


def _mock_client(monkeypatch, *, get_response=None, post_response=None, raise_error=False):
    async def fake_get(self, url, **kwargs):
        if raise_error:
            raise httpx.ConnectError("connection refused")
        return get_response

    async def fake_post(self, url, **kwargs):
        if raise_error:
            raise httpx.ConnectError("connection refused")
        return post_response

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)


def _response(json_body, status_code=200) -> httpx.Response:
    request = httpx.Request("GET", "http://localhost:11434/")
    return httpx.Response(status_code, json=json_body, request=request)


async def test_list_models_returns_names(monkeypatch):
    _mock_client(
        monkeypatch,
        get_response=_response({"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5"}]}),
    )
    provider = OllamaProvider("http://localhost:11434")
    models = await provider.list_models()
    assert models == ["llama3.2:latest", "qwen2.5"]


async def test_list_models_unreachable_raises_llm_unavailable(monkeypatch):
    _mock_client(monkeypatch, raise_error=True)
    provider = OllamaProvider("http://localhost:11434")
    with pytest.raises(LLMUnavailableError):
        await provider.list_models()


async def test_complete_without_schema_returns_raw_text(monkeypatch):
    _mock_client(monkeypatch, post_response=_response({"response": "hello world", "done": True}))
    provider = OllamaProvider("http://localhost:11434")
    result = await provider.complete("say hi", model="llama3.2")
    assert result == "hello world"


async def test_complete_with_schema_returns_validated_model(monkeypatch):
    _mock_client(monkeypatch, post_response=_response({"response": '{"ok": true}', "done": True}))
    provider = OllamaProvider("http://localhost:11434")
    result = await provider.complete("respond with json", model="llama3.2", schema=_Probe)
    assert isinstance(result, _Probe)
    assert result.ok is True


async def test_complete_with_schema_malformed_json_raises_validation_error(monkeypatch):
    _mock_client(
        monkeypatch, post_response=_response({"response": "not json at all", "done": True})
    )
    provider = OllamaProvider("http://localhost:11434")
    with pytest.raises(LLMValidationError):
        await provider.complete("respond with json", model="llama3.2", schema=_Probe)


async def test_complete_with_schema_wrong_shape_raises_validation_error(monkeypatch):
    _mock_client(
        monkeypatch,
        post_response=_response({"response": '{"unrelated_field": 1}', "done": True}),
    )
    provider = OllamaProvider("http://localhost:11434")
    with pytest.raises(LLMValidationError):
        await provider.complete("respond with json", model="llama3.2", schema=_Probe)


async def test_complete_unreachable_raises_llm_unavailable(monkeypatch):
    _mock_client(monkeypatch, raise_error=True)
    provider = OllamaProvider("http://localhost:11434")
    with pytest.raises(LLMUnavailableError):
        await provider.complete("say hi", model="llama3.2")

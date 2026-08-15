"""check_llm_health tests. Every path must return an LLMHealthStatus,
never raise — Section 36's "DO NOT crash entire application" applies at
every one of the four check stages.
"""

from __future__ import annotations

import httpx

from app.llm.health import check_llm_health


def _response(json_body, status_code=200) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost:11434/")
    return httpx.Response(status_code, json=json_body, request=request)


async def test_empty_model_reports_unhealthy_without_any_http_call(monkeypatch):
    async def fail_if_called(self, *a, **k):
        raise AssertionError("should not make an HTTP call with no model configured")

    monkeypatch.setattr(httpx.AsyncClient, "get", fail_if_called)
    monkeypatch.setattr(httpx.AsyncClient, "post", fail_if_called)

    status = await check_llm_health(base_url="http://localhost:11434", model="")
    assert status.healthy is False
    assert status.reachable is False
    assert "OLLAMA_MODEL" in (status.error or "")


async def test_unreachable_ollama_reports_unhealthy(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    status = await check_llm_health(base_url="http://localhost:11434", model="llama3.2")
    assert status.healthy is False
    assert status.reachable is False
    assert status.model_exists is False


async def test_model_not_found_reports_unhealthy_but_reachable(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return _response({"models": [{"name": "some-other-model"}]})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    status = await check_llm_health(base_url="http://localhost:11434", model="llama3.2")
    assert status.healthy is False
    assert status.reachable is True
    assert status.model_exists is False


async def test_model_exists_with_tag_suffix_matches_bare_name(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return _response({"models": [{"name": "llama3.2:latest"}]})

    async def fake_post(self, url, **kwargs):
        return _response({"response": '{"ok": true}'})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    status = await check_llm_health(base_url="http://localhost:11434", model="llama3.2")
    assert status.model_exists is True
    assert status.healthy is True


async def test_invalid_json_response_reports_unhealthy(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return _response({"models": [{"name": "llama3.2"}]})

    async def fake_post(self, url, **kwargs):
        return _response({"response": "not json"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    status = await check_llm_health(base_url="http://localhost:11434", model="llama3.2")
    assert status.reachable is True
    assert status.model_exists is True
    assert status.returns_valid_json is False
    assert status.healthy is False


async def test_structured_output_failure_reports_unhealthy(monkeypatch):
    call_count = 0

    async def fake_get(self, url, **kwargs):
        return _response({"models": [{"name": "llama3.2"}]})

    async def fake_post(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _response({"response": '{"ok": true}'})
        return _response({"response": "not valid json for the schema check"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    status = await check_llm_health(base_url="http://localhost:11434", model="llama3.2")
    assert status.returns_valid_json is True
    assert status.structured_output_valid is False
    assert status.healthy is False


async def test_all_checks_pass_reports_healthy(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return _response({"models": [{"name": "llama3.2"}]})

    async def fake_post(self, url, **kwargs):
        return _response({"response": '{"ok": true}'})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    status = await check_llm_health(base_url="http://localhost:11434", model="llama3.2")
    assert status.healthy is True
    assert status.error is None

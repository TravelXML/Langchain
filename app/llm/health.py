"""Startup health checks (Section 36): is Ollama reachable, does the
configured model exist, can it return valid JSON, does structured output
pass validation. Called once from `app.main`'s lifespan — the result is
logged, never raised. A fresh install with no Ollama running (or no
`OLLAMA_MODEL` set — both true by default, see `.env.example`) is
expected to fail every check here and must still serve every other
route normally; nothing in this app's request path depends on the LLM
being healthy.
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.llm.errors import LLMUnavailableError, LLMValidationError
from app.llm.ollama import OllamaProvider
from app.llm.schemas import LLMHealthStatus, _JSONCapabilityProbe

logger = get_logger(__name__)


async def check_llm_health(*, base_url: str, model: str) -> LLMHealthStatus:
    if not model:
        return LLMHealthStatus(
            reachable=False,
            model_exists=False,
            returns_valid_json=False,
            structured_output_valid=False,
            checked_model=model,
            error="OLLAMA_MODEL is not set",
        )

    provider = OllamaProvider(base_url)

    try:
        available_models = await provider.list_models()
    except LLMUnavailableError as exc:
        return LLMHealthStatus(
            reachable=False,
            model_exists=False,
            returns_valid_json=False,
            structured_output_valid=False,
            checked_model=model,
            error=str(exc),
        )

    # Ollama model names commonly carry a ":tag" suffix (":latest" by
    # default) — match on the bare name too, so a configured "llama3.2"
    # matches a pulled "llama3.2:latest".
    model_exists = model in available_models or any(
        m.split(":", 1)[0] == model for m in available_models
    )
    if not model_exists:
        return LLMHealthStatus(
            reachable=True,
            model_exists=False,
            returns_valid_json=False,
            structured_output_valid=False,
            checked_model=model,
            error=f"model {model!r} not found among: {available_models}",
        )

    try:
        raw = await provider.complete(
            "Respond with exactly this JSON object and nothing else: " '{"ok": true}',
            model=model,
        )
    except LLMUnavailableError as exc:
        return LLMHealthStatus(
            reachable=True,
            model_exists=True,
            returns_valid_json=False,
            structured_output_valid=False,
            checked_model=model,
            error=str(exc),
        )

    try:
        json.loads(raw)
        returns_valid_json = True
    except json.JSONDecodeError:
        returns_valid_json = False

    if not returns_valid_json:
        return LLMHealthStatus(
            reachable=True,
            model_exists=True,
            returns_valid_json=False,
            structured_output_valid=False,
            checked_model=model,
            error=f"model did not return valid JSON, got: {raw!r}",
        )

    try:
        await provider.complete(
            "Respond with a JSON object with one field, ok, set to true.",
            model=model,
            schema=_JSONCapabilityProbe,
        )
    except (LLMUnavailableError, LLMValidationError) as exc:
        return LLMHealthStatus(
            reachable=True,
            model_exists=True,
            returns_valid_json=True,
            structured_output_valid=False,
            checked_model=model,
            error=str(exc),
        )

    return LLMHealthStatus(
        reachable=True,
        model_exists=True,
        returns_valid_json=True,
        structured_output_valid=True,
        checked_model=model,
    )

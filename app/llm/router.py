"""Capability-based model routing (Section 37).

Every capability defaults to the same single configured model
(`llm.model` in `config/llm.yaml`) — the whole point is making a future
"use a stronger model for complex JD interpretation, a cheaper/faster one
for simple extraction" split a config-only change. Nothing in this
module cares which physical model backs a capability today.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.config import get_yaml_config_loader


class LLMCapability(StrEnum):
    SIMPLE_EXTRACTION = "simple_extraction"
    SEMANTIC_MATCHING = "semantic_matching"
    COMPLEX_INTERPRETATION = "complex_interpretation"
    COVER_LETTER = "cover_letter"


def model_for_capability(capability: LLMCapability) -> str:
    config = get_yaml_config_loader().load("llm")
    llm_config = config.get("llm", {})
    routing: dict[str, str] = llm_config.get("routing", {})
    return routing.get(capability.value) or llm_config.get("model", "")

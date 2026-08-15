from __future__ import annotations

from app.llm.router import LLMCapability, model_for_capability


def test_model_for_capability_uses_configured_routing(monkeypatch):
    from app.core.config import get_yaml_config_loader

    def fake_load(name: str):
        assert name == "llm"
        return {"llm": {"model": "default-model", "routing": {"cover_letter": "writer-model"}}}

    monkeypatch.setattr(get_yaml_config_loader(), "load", fake_load)

    assert model_for_capability(LLMCapability.COVER_LETTER) == "writer-model"


def test_model_for_capability_falls_back_to_base_model_when_unrouted(monkeypatch):
    from app.core.config import get_yaml_config_loader

    def fake_load(name: str):
        return {"llm": {"model": "default-model", "routing": {}}}

    monkeypatch.setattr(get_yaml_config_loader(), "load", fake_load)

    assert model_for_capability(LLMCapability.SIMPLE_EXTRACTION) == "default-model"


def test_model_for_capability_handles_missing_routing_key_entirely(monkeypatch):
    from app.core.config import get_yaml_config_loader

    def fake_load(name: str):
        return {"llm": {"model": "default-model"}}

    monkeypatch.setattr(get_yaml_config_loader(), "load", fake_load)

    assert model_for_capability(LLMCapability.SEMANTIC_MATCHING) == "default-model"


def test_every_capability_has_a_distinct_string_value():
    values = {c.value for c in LLMCapability}
    assert len(values) == len(list(LLMCapability))

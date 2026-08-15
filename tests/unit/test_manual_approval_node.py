"""Integration-level tests for manual_approval_node itself (as opposed
to test_apply_hybrid_approval.py's direct tests of the pure
`_hybrid_auto_approves` helper) — confirms the node reads
`config/automation.yaml`'s `approval` section correctly and that hybrid
mode genuinely skips the `interrupt()` call when it auto-approves.
"""

from __future__ import annotations

from app.browser.models import FieldMapping
from app.core.config import get_yaml_config_loader
from app.graph.apply_nodes import manual_approval_node
from app.jobs.models import NormalizedJob


def _job() -> NormalizedJob:
    return NormalizedJob(
        id="job-1",
        source="test",
        url="https://example.com/jobs/1",
        title="CTO",
        company="Acme",
        description="",
        discovered_at="2026-08-14T00:00:00Z",
    )


def _mapping(confidence: float, requires_human: bool = False) -> FieldMapping:
    return FieldMapping(
        field="email",
        candidate_value="x@example.com" if not requires_human else None,
        confidence=confidence,
        requires_human=requires_human,
        source="profile" if not requires_human else "unmapped",
        reason="test",
    )


def _patch_automation_config(monkeypatch, approval_config: dict) -> None:
    loader = get_yaml_config_loader()

    def fake_load(name: str):
        if name == "automation":
            return {"approval": approval_config}
        return {}

    monkeypatch.setattr(loader, "load", fake_load)


async def test_automatic_mode_approves_without_interrupt(monkeypatch):
    _patch_automation_config(monkeypatch, {"mode": "automatic"})
    result = await manual_approval_node({"job": _job(), "field_mappings": [], "match_score": None})
    assert result == {"approved": True}


async def test_hybrid_mode_auto_approves_without_interrupt_when_bar_cleared(monkeypatch):
    _patch_automation_config(
        monkeypatch, {"mode": "hybrid", "hybrid_min_score": 90, "hybrid_min_confidence": 0.85}
    )
    result = await manual_approval_node(
        {"job": _job(), "field_mappings": [_mapping(0.95)], "match_score": 95.0}
    )
    assert result == {"approved": True}


async def test_hybrid_mode_falls_through_to_interrupt_when_score_missing(monkeypatch):
    _patch_automation_config(
        monkeypatch, {"mode": "hybrid", "hybrid_min_score": 90, "hybrid_min_confidence": 0.85}
    )
    # No score -> _hybrid_auto_approves is False -> falls through to the
    # same interrupt() call "manual" mode uses. Called outside a real
    # graph run (no checkpointer/runnable context here), interrupt()
    # raises rather than pausing — that raise is exactly the proof the
    # auto-approve shortcut was *not* taken (see the full pause/resume
    # behavior verified for real in tests/e2e/test_apply_graph.py).
    raised = False
    try:
        await manual_approval_node(
            {"job": _job(), "field_mappings": [_mapping(0.95)], "match_score": None}
        )
    except RuntimeError:
        raised = True
    assert raised


async def test_manual_mode_never_auto_approves_even_with_perfect_state(monkeypatch):
    _patch_automation_config(monkeypatch, {"mode": "manual"})
    try:
        await manual_approval_node(
            {"job": _job(), "field_mappings": [_mapping(0.99)], "match_score": 100.0}
        )
        raised = False
    except RuntimeError:
        raised = True
    # Manual mode always requests a human decision via interrupt() —
    # calling this node outside a real graph run means interrupt()
    # raises rather than pausing, which is exactly the proof we want:
    # the auto-approve path was never taken.
    assert raised

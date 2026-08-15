"""Unit tests for the portal registry itself (Phase 10) — the mechanism
that lets `app/graph/nodes.py` dispatch to any registered adapter without
a per-portal branch.
"""

from __future__ import annotations

from app.portals.greenhouse.adapter import GreenhouseAdapter
from app.portals.lever.adapter import LeverAdapter
from app.portals.registry import build_adapter, resolve_enabled_real_portals


def test_resolve_enabled_real_portals_empty_config():
    assert resolve_enabled_real_portals({}) == []
    assert resolve_enabled_real_portals({"portals": {}}) == []


def test_resolve_enabled_real_portals_greenhouse_only():
    config = {"portals": {"greenhouse": {"boards": ["gitlab", "acme"]}}}
    assert resolve_enabled_real_portals(config) == ["greenhouse:gitlab", "greenhouse:acme"]


def test_resolve_enabled_real_portals_lever_only():
    config = {"portals": {"lever": {"companies": ["leverdemo"]}}}
    assert resolve_enabled_real_portals(config) == ["lever:leverdemo"]


def test_resolve_enabled_real_portals_combines_multiple_portals():
    config = {
        "portals": {
            "greenhouse": {"boards": ["gitlab"]},
            "lever": {"companies": ["leverdemo"]},
        }
    }
    result = resolve_enabled_real_portals(config)
    assert set(result) == {"greenhouse:gitlab", "lever:leverdemo"}


def test_build_adapter_greenhouse():
    adapter = build_adapter("greenhouse:gitlab")
    assert isinstance(adapter, GreenhouseAdapter)
    assert adapter.board_token == "gitlab"


def test_build_adapter_lever():
    adapter = build_adapter("lever:leverdemo")
    assert isinstance(adapter, LeverAdapter)
    assert adapter.company == "leverdemo"


def test_build_adapter_unknown_prefix_returns_none():
    assert build_adapter("workday:acme") is None


def test_build_adapter_no_prefix_returns_none():
    assert build_adapter("mock_greenhouse") is None

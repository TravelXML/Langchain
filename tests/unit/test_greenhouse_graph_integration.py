"""Proves config/portals.yaml's default (empty boards/companies) leaves
Phase 3's mock-portal behavior completely unchanged, and that a
configured Greenhouse board correctly routes discovery through the
portal registry (Phase 10) — without any live network call in this test.
"""

from __future__ import annotations

from app.graph import nodes
from app.portals import registry


async def test_default_config_still_falls_back_to_mock_portals():
    """config/portals.yaml ships with empty identifier lists for every
    portal — this must keep exercising exactly Phase 3's original
    behavior."""
    result = await nodes.load_search_policy_node({})
    assert set(result["enabled_portals"]) == set(nodes.MOCK_PORTALS.keys())


async def test_configured_board_takes_priority_over_mock_portals(monkeypatch):
    from app.core.config import get_yaml_config_loader

    loader = get_yaml_config_loader()

    def fake_load(name: str):
        if name == "portals":
            return {"portals": {"greenhouse": {"boards": ["acme"]}}}
        return {"search": {}}

    monkeypatch.setattr(loader, "load", fake_load)

    result = await nodes.load_search_policy_node({})
    assert result["enabled_portals"] == ["greenhouse:acme"]


async def test_discover_portal_node_delegates_to_greenhouse_adapter(monkeypatch):
    class _FakeAdapter:
        def __init__(self, board_token: str) -> None:
            self.board_token = board_token

        async def discover_jobs(self, search_policy):
            return [
                {
                    "external_job_id": "1",
                    "url": "https://job-boards.greenhouse.io/acme/jobs/1",
                    "title": "Staff Engineer",
                    "company": "Acme",
                }
            ]

    monkeypatch.setitem(
        registry.PORTAL_REGISTRY,
        "greenhouse",
        registry.PortalRegistration("greenhouse", "boards", _FakeAdapter),
    )

    result = await nodes.discover_portal_node(
        {"current_portal": "greenhouse:acme", "search_policy": {}}
    )

    assert len(result["discovered_jobs"]) == 1
    assert result["discovered_jobs"][0]["_source"] == "greenhouse:acme"
    assert result["discovered_jobs"][0]["title"] == "Staff Engineer"


async def test_discover_portal_node_reports_greenhouse_failure_without_raising(monkeypatch):
    class _FailingAdapter:
        def __init__(self, board_token: str) -> None:
            self.board_token = board_token

        async def discover_jobs(self, search_policy):
            raise RuntimeError("board not found")

    monkeypatch.setitem(
        registry.PORTAL_REGISTRY,
        "greenhouse",
        registry.PortalRegistration("greenhouse", "boards", _FailingAdapter),
    )

    result = await nodes.discover_portal_node(
        {"current_portal": "greenhouse:does-not-exist", "search_policy": {}}
    )

    assert "discovered_jobs" not in result
    assert result["errors"][0]["portal"] == "greenhouse:does-not-exist"


async def test_mock_portal_still_routes_correctly_alongside_greenhouse_support():
    result = await nodes.discover_portal_node({"current_portal": "mock_greenhouse"})
    assert len(result["discovered_jobs"]) == 3
    assert all(j["_source"] == "mock_greenhouse" for j in result["discovered_jobs"])

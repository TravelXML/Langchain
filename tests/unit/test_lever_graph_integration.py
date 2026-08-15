"""Proves a configured Lever company correctly routes discovery through
the portal registry (Phase 10) — without any live network call in this
test, and without any Lever-specific code in app/graph/nodes.py.
"""

from __future__ import annotations

from app.graph import nodes
from app.portals import registry


async def test_configured_company_takes_priority_over_mock_portals(monkeypatch):
    from app.core.config import get_yaml_config_loader

    loader = get_yaml_config_loader()

    def fake_load(name: str):
        if name == "portals":
            return {"portals": {"lever": {"companies": ["leverdemo"]}}}
        return {"search": {}}

    monkeypatch.setattr(loader, "load", fake_load)

    result = await nodes.load_search_policy_node({})
    assert result["enabled_portals"] == ["lever:leverdemo"]


async def test_discover_portal_node_delegates_to_lever_adapter(monkeypatch):
    class _FakeAdapter:
        def __init__(self, company: str) -> None:
            self.company = company

        async def discover_jobs(self, search_policy):
            return [
                {
                    "external_job_id": "abc",
                    "url": "https://jobs.lever.co/leverdemo/abc",
                    "title": "Staff Engineer",
                    "company": "leverdemo",
                }
            ]

    monkeypatch.setitem(
        registry.PORTAL_REGISTRY,
        "lever",
        registry.PortalRegistration("lever", "companies", _FakeAdapter),
    )

    result = await nodes.discover_portal_node(
        {"current_portal": "lever:leverdemo", "search_policy": {}}
    )

    assert len(result["discovered_jobs"]) == 1
    assert result["discovered_jobs"][0]["_source"] == "lever:leverdemo"
    assert result["discovered_jobs"][0]["title"] == "Staff Engineer"


async def test_discover_portal_node_reports_lever_failure_without_raising(monkeypatch):
    class _FailingAdapter:
        def __init__(self, company: str) -> None:
            self.company = company

        async def discover_jobs(self, search_policy):
            raise RuntimeError("company not found")

    monkeypatch.setitem(
        registry.PORTAL_REGISTRY,
        "lever",
        registry.PortalRegistration("lever", "companies", _FailingAdapter),
    )

    result = await nodes.discover_portal_node(
        {"current_portal": "lever:does-not-exist", "search_policy": {}}
    )

    assert "discovered_jobs" not in result
    assert result["errors"][0]["portal"] == "lever:does-not-exist"


async def test_both_greenhouse_and_lever_can_be_enabled_together(monkeypatch):
    from app.core.config import get_yaml_config_loader

    loader = get_yaml_config_loader()

    def fake_load(name: str):
        if name == "portals":
            return {
                "portals": {
                    "greenhouse": {"boards": ["gitlab"]},
                    "lever": {"companies": ["leverdemo"]},
                }
            }
        return {"search": {}}

    monkeypatch.setattr(loader, "load", fake_load)

    result = await nodes.load_search_policy_node({})
    assert set(result["enabled_portals"]) == {"greenhouse:gitlab", "lever:leverdemo"}

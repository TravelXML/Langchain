"""Portal adapter registry (Phase 10: "add each portal as an isolated
adapter/subgraph — do not modify the supervisor for every new portal").

`app/graph/nodes.py` depends only on this module — `resolve_enabled_real_portals`
and `build_adapter` — never on a specific adapter class. Adding a third
portal means adding a new `app/portals/<name>/` module plus one entry
here; `nodes.py` itself needs zero changes.

(Phase 7 originally wired Greenhouse directly into `nodes.py` — a
`portal.startswith("greenhouse:")` branch. Phase 10 pulls that out into
this registry rather than adding a second, near-identical branch for
Lever, which is exactly the "modify the supervisor for every new portal"
pattern the phase spec rules out.)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.portals.base import JobPortalAdapter
from app.portals.greenhouse.adapter import GreenhouseAdapter
from app.portals.lever.adapter import LeverAdapter


@dataclass(frozen=True)
class PortalRegistration:
    prefix: str
    # Key under config/portals.yaml's `portals.<prefix>` section listing
    # this portal's board/company identifiers — each portal names its own
    # identifier concept (Greenhouse: "boards", Lever: "companies"), so
    # this isn't forced into one shared term.
    identifiers_key: str
    factory: Callable[[str], JobPortalAdapter]


PORTAL_REGISTRY: dict[str, PortalRegistration] = {
    "greenhouse": PortalRegistration("greenhouse", "boards", GreenhouseAdapter),
    "lever": PortalRegistration("lever", "companies", LeverAdapter),
}


def resolve_enabled_real_portals(portals_config: dict[str, Any]) -> list[str]:
    """Every configured real-portal identifier, as fully-qualified portal
    ids (``"greenhouse:gitlab"``, ``"lever:acme"``) — empty if nothing is
    configured, so a fresh install (every `config/portals.yaml` section
    ships with an empty identifier list) falls back to mock portals.
    """
    portals_section = portals_config.get("portals", {})
    enabled: list[str] = []
    for prefix, registration in PORTAL_REGISTRY.items():
        identifiers = portals_section.get(prefix, {}).get(registration.identifiers_key, [])
        enabled.extend(f"{prefix}:{identifier}" for identifier in identifiers)
    return enabled


def build_adapter(portal_id: str) -> JobPortalAdapter | None:
    """``"greenhouse:gitlab"`` -> a ready ``GreenhouseAdapter("gitlab")``.
    ``None`` for an unrecognized prefix — the caller (`discover_portal_node`)
    treats that the same as any other unconfigured portal.
    """
    prefix, _, identifier = portal_id.partition(":")
    registration = PORTAL_REGISTRY.get(prefix)
    if registration is None:
        return None
    return registration.factory(identifier)

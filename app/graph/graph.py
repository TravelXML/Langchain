"""Supervisor graph wiring: nodes, edges, routing, persistence (Section 4/23/26).

The supervisor itself dispatches discovery to every enabled portal in
parallel (Section 24's fan-out) via LangGraph's ``Send`` API — it does not
touch scoring, DB access, or policy decisions directly, all of which are
plain deterministic code in ``nodes.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from app.core.config import get_settings
from app.graph import nodes
from app.graph.state import JobAutomationState, ScoredJob
from app.jobs.models import NormalizedJob
from app.matching.models import MatchResult
from app.profile.models import CandidateProfile

# The checkpointer serializes graph state to msgpack between steps and runs.
# By default it refuses (with a deprecation warning today, a hard error in a
# future langgraph release) to deserialize custom classes it doesn't
# recognize — these are exactly the Pydantic models this graph's state
# carries, so they need to be explicitly allow-listed.
_ALLOWED_CHECKPOINT_TYPES = [CandidateProfile, NormalizedJob, MatchResult, ScoredJob]


def _fan_out_to_portals(state: JobAutomationState) -> list[Send]:
    return [
        Send("discover_portal", {"current_portal": portal})
        for portal in state.get("enabled_portals", [])
    ]


def build_graph() -> StateGraph:
    graph = StateGraph(JobAutomationState)

    graph.add_node("load_candidate_profile", nodes.load_candidate_profile_node)
    graph.add_node("load_search_policy", nodes.load_search_policy_node)
    graph.add_node("discover_portal", nodes.discover_portal_node)
    graph.add_node("normalize_jobs", nodes.normalize_jobs_node)
    graph.add_node("dedupe_jobs", nodes.dedupe_jobs_node)
    graph.add_node("score_jobs", nodes.score_jobs_node)
    graph.add_node("policy_guard", nodes.policy_guard_node)
    graph.add_node("finalize", nodes.finalize_node)

    graph.add_edge(START, "load_candidate_profile")
    graph.add_edge("load_candidate_profile", "load_search_policy")
    graph.add_conditional_edges("load_search_policy", _fan_out_to_portals, ["discover_portal"])
    graph.add_edge("discover_portal", "normalize_jobs")
    graph.add_edge("normalize_jobs", "dedupe_jobs")
    graph.add_edge("dedupe_jobs", "score_jobs")
    graph.add_edge("score_jobs", "policy_guard")
    graph.add_edge("policy_guard", "finalize")
    graph.add_edge("finalize", END)

    return graph


@asynccontextmanager
async def compiled_graph() -> AsyncIterator[CompiledStateGraph]:
    """Yields a graph compiled with a checkpointer bound to the configured
    SQLite file — a fresh connection per call, so run state genuinely
    survives process restarts rather than living in Python memory
    (Section 26)."""
    path = get_settings().langgraph_checkpoint_path
    serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_CHECKPOINT_TYPES)
    async with aiosqlite.connect(path) as conn:
        checkpointer = AsyncSqliteSaver(conn, serde=serde)
        yield build_graph().compile(checkpointer=checkpointer)

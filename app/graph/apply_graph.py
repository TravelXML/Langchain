"""Apply-subgraph wiring (Section 10/19, Phase 6).

START -> detect_and_map_fields -> fill_and_validate -> check_challenges ->
manual_approval -> finalize_application -> END

Linear on purpose: one job, one form, processed start to finish — no
fan-out (Section 24's ``application_concurrency: 1`` default already rules
out parallel applications; Phase 7 is what will invoke one of these graphs
per queued job, sequentially).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.browser.models import FieldMapping
from app.core.config import get_settings
from app.graph import apply_nodes
from app.graph.apply_state import ApplicationState
from app.jobs.models import NormalizedJob
from app.profile.models import CandidateProfile

_ALLOWED_CHECKPOINT_TYPES = [CandidateProfile, NormalizedJob, FieldMapping]


def build_apply_graph() -> StateGraph:
    graph = StateGraph(ApplicationState)

    graph.add_node("detect_and_map_fields", apply_nodes.detect_and_map_fields_node)
    graph.add_node("fill_and_validate", apply_nodes.fill_and_validate_node)
    graph.add_node("check_challenges", apply_nodes.check_challenges_node)
    graph.add_node("manual_approval", apply_nodes.manual_approval_node)
    graph.add_node("finalize_application", apply_nodes.finalize_application_node)

    graph.add_edge(START, "detect_and_map_fields")
    graph.add_edge("detect_and_map_fields", "fill_and_validate")
    graph.add_edge("fill_and_validate", "check_challenges")
    graph.add_edge("check_challenges", "manual_approval")
    graph.add_edge("manual_approval", "finalize_application")
    graph.add_edge("finalize_application", END)

    return graph


@asynccontextmanager
async def compiled_apply_graph() -> AsyncIterator[CompiledStateGraph]:
    """A fresh checkpointer connection per call — same rationale as
    ``app.graph.graph.compiled_graph``: proves an application genuinely
    resumes from disk, not from anything held in Python memory."""
    path = get_settings().langgraph_checkpoint_path
    serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_CHECKPOINT_TYPES)
    async with aiosqlite.connect(path) as conn:
        checkpointer = AsyncSqliteSaver(conn, serde=serde)
        yield build_apply_graph().compile(checkpointer=checkpointer)

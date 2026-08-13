from __future__ import annotations

from app.graph import nodes
from app.jobs.parser import normalize_job


async def test_discover_portal_node_tags_jobs_with_source():
    result = await nodes.discover_portal_node({"current_portal": "mock_greenhouse"})
    jobs = result["discovered_jobs"]
    assert len(jobs) == 3
    assert all(j["_source"] == "mock_greenhouse" for j in jobs)


async def test_discover_portal_node_unknown_portal_warns_without_raising():
    result = await nodes.discover_portal_node({"current_portal": "not_a_real_portal"})
    assert "discovered_jobs" not in result
    assert result["warnings"]


async def test_normalize_jobs_node_converts_raw_dicts():
    raw = {
        "url": "https://example.com/1",
        "title": "CTO",
        "company": "Acme",
        "_source": "mock_greenhouse",
    }
    result = await nodes.normalize_jobs_node({"discovered_jobs": [raw]})
    assert len(result["normalized_jobs"]) == 1
    assert result["normalized_jobs"][0].source == "mock_greenhouse"


async def test_normalize_jobs_node_collects_errors_for_invalid_job():
    raw = {"url": "https://example.com/1", "_source": "mock_greenhouse"}  # missing title/company
    result = await nodes.normalize_jobs_node({"discovered_jobs": [raw]})
    assert result["normalized_jobs"] == []
    assert result["errors"]


async def test_dedupe_jobs_node_collapses_cross_portal_duplicate():
    job_a = normalize_job(
        {
            "url": "https://boards.greenhouse.io/acme/101",
            "title": "CTO",
            "company": "Acme SaaS",
            "location": "Bengaluru, India",
        },
        source="mock_greenhouse",
    )
    job_b = normalize_job(
        {
            "url": "https://jobs.lever.co/acme/201",
            "title": "Chief Technology Officer",
            "company": "Acme SaaS",
            "location": "Bengaluru, India",
        },
        source="mock_lever",
    )
    result = await nodes.dedupe_jobs_node({"normalized_jobs": [job_a, job_b]})
    assert len(result["normalized_jobs"]) == 1
    assert len(result["duplicate_jobs"]) == 1


async def test_dedupe_jobs_node_keeps_distinct_jobs():
    job_a = normalize_job(
        {"url": "https://x/1", "title": "CTO", "company": "Acme", "location": "Bengaluru"},
        source="a",
    )
    job_b = normalize_job(
        {"url": "https://x/2", "title": "IT Director", "company": "Beta", "location": "Berlin"},
        source="b",
    )
    result = await nodes.dedupe_jobs_node({"normalized_jobs": [job_a, job_b]})
    assert len(result["normalized_jobs"]) == 2
    assert result["duplicate_jobs"] == []


async def test_policy_guard_node_splits_without_interrupt_when_no_human_review():
    from app.graph.state import ScoredJob
    from app.matching.models import MatchResult, ScoreBreakdown
    from tests.fixtures.job_builder import make_job

    breakdown = ScoreBreakdown(
        title=25, skills=30, experience=15, industry=10, location=10, compensation=10
    )
    good = ScoredJob(
        job=make_job(id="j1"),
        match=MatchResult(
            overall_score=95,
            breakdown=breakdown,
            reason="great fit",
            recommendation="priority_apply",
        ),
    )
    bad = ScoredJob(
        job=make_job(id="j2"),
        match=MatchResult(
            overall_score=10,
            breakdown=breakdown,
            reason="poor fit",
            recommendation="reject",
        ),
    )
    result = await nodes.policy_guard_node({"scored_jobs": [good, bad]})
    assert [s.job.id for s in result["application_queue"]] == ["j1"]
    assert [s.job.id for s in result["rejected_jobs"]] == ["j2"]
    assert result["human_action_required"] is False


async def test_finalize_node_computes_metrics():
    result = await nodes.finalize_node(
        {
            "discovered_jobs": [{}, {}],
            "duplicate_jobs": [object()],
            "scored_jobs": [object(), object()],
            "rejected_jobs": [object()],
            "application_queue": [object()],
            "human_review_jobs": [],
        }
    )
    assert result["metrics"] == {
        "discovered": 2,
        "duplicates": 1,
        "scored": 2,
        "rejected": 1,
        "queued": 1,
        "human_review_pending": 0,
    }

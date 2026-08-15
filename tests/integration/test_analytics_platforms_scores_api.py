from __future__ import annotations

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction

_PREFERENCES = CandidatePreferences(
    target_positions=["CTO"],
    preferred_industries=["SaaS"],
    skills_primary=["Cloud Architecture", "Engineering Leadership", "AWS", "Python"],
    locations_preferred=["Bengaluru", "Remote"],
    relocation_allowed=False,
    work_mode=["remote", "hybrid"],
    compensation_currency="INR",
    compensation_minimum=30,
    compensation_preferred=50,
    work_authorization="citizen",
)


async def _seed_profile() -> None:
    resume = ResumeExtraction(
        source_file="resume.pdf",
        raw_text="...",
        email=ExtractedField[str](value="jordan@example.com", source="resume", confidence=0.95),
        experience_years=ExtractedField[float](value=15.0, source="resume", confidence=0.7),
    )
    async with get_sessionmaker()() as session:
        session.add(
            CandidateProfileRecord(
                id=DEFAULT_PROFILE_ID,
                preferences=_PREFERENCES.model_dump(mode="json"),
                resume=resume.model_dump(mode="json"),
            )
        )
        await session.commit()


async def _run_discovery_to_completion(client) -> dict:
    create_response = await client.post("/api/runs")
    body = create_response.json()
    run_id = body["run_id"]
    pending_job_id = body["interrupt"]["jobs"][0]["job_id"]
    resume_response = await client.post(
        f"/api/runs/{run_id}/resume", json={"decisions": {pending_job_id: "queue"}}
    )
    return resume_response.json()


async def test_analytics_platforms_breaks_down_by_source(client):
    await _seed_profile()
    await _run_discovery_to_completion(client)

    response = await client.get("/api/analytics/platforms")
    assert response.status_code == 200
    body = response.json()
    assert body["platforms"], "expected at least one platform breakdown"
    total_discovered = sum(p["jobs_discovered"] for p in body["platforms"])
    assert total_discovered > 0
    for platform in body["platforms"]:
        assert platform["source"]
        assert platform["jobs_discovered"] >= platform["jobs_queued"]


async def test_analytics_platforms_empty_when_no_data(client):
    response = await client.get("/api/analytics/platforms")
    assert response.status_code == 200
    assert response.json()["platforms"] == []


async def test_analytics_scores_summarizes_scored_jobs(client):
    await _seed_profile()
    await _run_discovery_to_completion(client)

    response = await client.get("/api/analytics/scores")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] > 0
    assert body["min_score"] is not None
    assert body["max_score"] is not None
    assert body["min_score"] <= body["average_score"] <= body["max_score"]
    assert sum(body["score_buckets"].values()) == body["count"]
    assert set(body["average_breakdown"].keys()) <= {
        "title",
        "skills",
        "experience",
        "industry",
        "location",
        "compensation",
    }


async def test_analytics_scores_empty_when_no_data(client):
    response = await client.get("/api/analytics/scores")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["min_score"] is None
    assert body["average_breakdown"] == {}

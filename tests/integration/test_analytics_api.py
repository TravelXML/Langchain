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


async def test_analytics_summary_reflects_persisted_jobs(client):
    await _seed_profile()

    empty_response = await client.get("/api/analytics/summary")
    assert empty_response.status_code == 200
    empty_body = empty_response.json()
    assert empty_body["jobs_discovered_today"] == 0
    assert empty_body["jobs_by_status"] == {}
    assert empty_body["human_review_pending"] == 0

    create_response = await client.post("/api/runs")
    body = create_response.json()
    run_id = body["run_id"]
    pending_job_id = body["interrupt"]["jobs"][0]["job_id"]
    await client.post(f"/api/runs/{run_id}/resume", json={"decisions": {pending_job_id: "queue"}})

    summary_response = await client.get("/api/analytics/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()

    assert summary["jobs_discovered_today"] > 0
    assert sum(summary["jobs_by_status"].values()) == summary["jobs_discovered_today"]
    assert "queued" in summary["jobs_by_status"]

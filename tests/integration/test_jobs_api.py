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
    assert create_response.status_code == 200
    body = create_response.json()
    run_id = body["run_id"]
    pending_job_id = body["interrupt"]["jobs"][0]["job_id"]
    resume_response = await client.post(
        f"/api/runs/{run_id}/resume", json={"decisions": {pending_job_id: "queue"}}
    )
    assert resume_response.status_code == 200
    return resume_response.json()


async def test_jobs_are_persisted_after_a_run(client):
    await _seed_profile()
    result = await _run_discovery_to_completion(client)
    assert result["metrics"]["queued"] >= 1

    list_response = await client.get("/api/jobs")
    assert list_response.status_code == 200
    jobs = list_response.json()
    # Duplicates are persisted too (status="duplicate"), so total rows ==
    # discovered, not discovered - duplicates.
    assert len(jobs) == result["metrics"]["discovered"]

    queued = [j for j in jobs if j["status"] == "queued"]
    assert len(queued) == result["metrics"]["queued"]
    assert queued[0]["overall_score"] is not None
    assert queued[0]["breakdown"] is not None


async def test_jobs_status_filter(client):
    await _seed_profile()
    await _run_discovery_to_completion(client)

    rejected_response = await client.get("/api/jobs", params={"status": "rejected"})
    assert rejected_response.status_code == 200
    for job in rejected_response.json():
        assert job["status"] == "rejected"


async def test_jobs_min_score_filter(client):
    await _seed_profile()
    await _run_discovery_to_completion(client)

    response = await client.get("/api/jobs", params={"status": "queued", "min_score": 999})
    assert response.status_code == 200
    assert response.json() == []


async def test_get_job_by_id(client):
    await _seed_profile()
    await _run_discovery_to_completion(client)

    jobs = (await client.get("/api/jobs")).json()
    job_id = jobs[0]["id"]

    response = await client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["id"] == job_id


async def test_get_unknown_job_returns_404(client):
    response = await client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404

from __future__ import annotations

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction

# work_authorization is set so this API-level test isn't also tripping the
# Phase 4 guardrail that flags an unset value as needing human input.
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


async def test_run_lifecycle_via_api(client):
    await _seed_profile()

    create_response = await client.post("/api/runs")
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["status"] == "waiting_human"
    run_id = body["run_id"]

    get_response = await client.get(f"/api/runs/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "waiting_human"

    pending_job_id = body["interrupt"]["jobs"][0]["job_id"]
    resume_response = await client.post(
        f"/api/runs/{run_id}/resume", json={"decisions": {pending_job_id: "queue"}}
    )
    assert resume_response.status_code == 200
    resumed_body = resume_response.json()
    assert resumed_body["status"] == "completed"
    assert resumed_body["metrics"]["queued"] >= 1


async def test_get_unknown_run_returns_404(client):
    response = await client.get("/api/runs/does-not-exist")
    assert response.status_code == 404


async def test_resume_unknown_run_returns_404(client):
    response = await client.post("/api/runs/does-not-exist/resume", json={"decisions": {}})
    assert response.status_code == 404

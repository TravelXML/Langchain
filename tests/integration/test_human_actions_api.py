from __future__ import annotations

from pathlib import Path

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction
from tests.fixtures.job_builder import make_job

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "html"

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


def _fixture_url(name: str) -> str:
    return f"file://{_FIXTURES_DIR / name}"


async def _seed_profile() -> None:
    resume = ResumeExtraction(
        source_file="resume.pdf",
        raw_text="...",
        email=ExtractedField[str](value="jordan@example.com", source="resume", confidence=0.95),
        name=ExtractedField[str](value="Jordan Casey Smith", source="resume", confidence=0.8),
        phone=ExtractedField[str](value="+1 415 555 0134", source="resume", confidence=0.8),
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


async def test_run_intervention_appears_and_resolves(client):
    await _seed_profile()

    create_response = await client.post("/api/runs")
    body = create_response.json()
    run_id = body["run_id"]

    pending_response = await client.get("/api/human-actions")
    assert pending_response.status_code == 200
    pending = pending_response.json()
    run_entries = [p for p in pending if p["kind"] == "run" and p["ref_id"] == run_id]
    assert len(run_entries) == 1
    intervention_id = run_entries[0]["id"]

    pending_job_id = body["interrupt"]["jobs"][0]["job_id"]
    resolve_response = await client.post(
        f"/api/human-actions/{intervention_id}/resolve",
        json={"decisions": {pending_job_id: "queue"}},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "completed"

    pending_after = (await client.get("/api/human-actions")).json()
    assert all(p["ref_id"] != run_id for p in pending_after)


async def test_application_intervention_appears_and_resolves(client):
    await _seed_profile()
    job = make_job()

    create_response = await client.post(
        "/api/applications",
        json={
            "job": job.model_dump(mode="json"),
            "form_page_url": _fixture_url("simple_application_form.html"),
        },
    )
    application_id = create_response.json()["application_id"]

    pending = (await client.get("/api/human-actions")).json()
    app_entries = [
        p for p in pending if p["kind"] == "application" and p["ref_id"] == application_id
    ]
    assert len(app_entries) == 1
    intervention_id = app_entries[0]["id"]

    resolve_response = await client.post(
        f"/api/human-actions/{intervention_id}/resolve",
        json={"payload": {"approved": True}},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "completed"

    pending_after = (await client.get("/api/human-actions")).json()
    assert all(p["ref_id"] != application_id for p in pending_after)


async def test_resolve_run_intervention_without_decisions_returns_422(client):
    await _seed_profile()
    create_response = await client.post("/api/runs")
    run_id = create_response.json()["run_id"]

    pending = (await client.get("/api/human-actions")).json()
    intervention_id = next(p["id"] for p in pending if p["ref_id"] == run_id)

    response = await client.post(f"/api/human-actions/{intervention_id}/resolve", json={})
    assert response.status_code == 422


async def test_resolve_unknown_intervention_returns_404(client):
    response = await client.post(
        "/api/human-actions/does-not-exist/resolve", json={"decisions": {}}
    )
    assert response.status_code == 404

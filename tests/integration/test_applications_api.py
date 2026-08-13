from __future__ import annotations

from pathlib import Path

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction
from tests.fixtures.job_builder import make_job

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "html"


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
                preferences=CandidatePreferences().model_dump(mode="json"),
                resume=resume.model_dump(mode="json"),
            )
        )
        await session.commit()


async def test_application_lifecycle_via_api(client):
    await _seed_profile()
    job = make_job()

    create_response = await client.post(
        "/api/applications",
        json={
            "job": job.model_dump(mode="json"),
            "form_page_url": _fixture_url("simple_application_form.html"),
        },
    )
    assert create_response.status_code == 200, create_response.text
    body = create_response.json()
    assert body["status"] == "waiting_human"
    assert body["interrupt"]["reason"] == "MANUAL_APPROVAL_REQUIRED"
    application_id = body["application_id"]

    get_response = await client.get(f"/api/applications/{application_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "waiting_human"

    resume_response = await client.post(
        f"/api/applications/{application_id}/resume", json={"payload": {"approved": True}}
    )
    assert resume_response.status_code == 200
    resumed_body = resume_response.json()
    assert resumed_body["status"] == "completed"
    assert resumed_body["application_status"] == "dry_run_ready"


async def test_get_unknown_application_returns_404(client):
    response = await client.get("/api/applications/does-not-exist")
    assert response.status_code == 404


async def test_resume_unknown_application_returns_404(client):
    response = await client.post("/api/applications/does-not-exist/resume", json={"payload": {}})
    assert response.status_code == 404


async def test_create_application_without_profile_returns_409(client):
    job = make_job()
    response = await client.post(
        "/api/applications",
        json={
            "job": job.model_dump(mode="json"),
            "form_page_url": _fixture_url("simple_application_form.html"),
        },
    )
    assert response.status_code == 409

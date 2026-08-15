"""Confirms graph/service.py and graph/apply_service.py actually call
notify_all with the right NotificationKind at the right points (Section
35's "Notify on" list) — not just that the notification module works in
isolation (see tests/unit/test_notifications.py).
"""

from __future__ import annotations

from pathlib import Path

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.notifications.models import NotificationKind
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction
from tests.fixtures.job_builder import make_job

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "html"

_RUN_PREFERENCES = CandidatePreferences(
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


async def _seed_profile(*, with_name_and_phone: bool) -> None:
    extra = {}
    if with_name_and_phone:
        extra["name"] = ExtractedField[str](
            value="Jordan Casey Smith", source="resume", confidence=0.8
        )
        extra["phone"] = ExtractedField[str](
            value="+1 415 555 0134", source="resume", confidence=0.8
        )
    resume = ResumeExtraction(
        source_file="resume.pdf",
        raw_text="...",
        email=ExtractedField[str](value="jordan@example.com", source="resume", confidence=0.95),
        experience_years=ExtractedField[float](value=15.0, source="resume", confidence=0.7),
        **extra,
    )
    async with get_sessionmaker()() as session:
        session.add(
            CandidateProfileRecord(
                id=DEFAULT_PROFILE_ID,
                preferences=_RUN_PREFERENCES.model_dump(mode="json"),
                resume=resume.model_dump(mode="json"),
            )
        )
        await session.commit()


def _patch_notify(monkeypatch, module_path: str) -> list[NotificationKind]:
    calls: list[NotificationKind] = []

    async def fake_notify_all(event):
        calls.append(event.kind)

    monkeypatch.setattr(f"{module_path}.notify_all", fake_notify_all)
    return calls


async def test_run_notifies_human_review_then_completed(client, monkeypatch):
    run_calls = _patch_notify(monkeypatch, "app.graph.service")
    await _seed_profile(with_name_and_phone=True)

    create_response = await client.post("/api/runs")
    body = create_response.json()
    assert run_calls == [NotificationKind.HUMAN_INTERVENTION_REQUIRED]

    pending_job_id = body["interrupt"]["jobs"][0]["job_id"]
    await client.post(
        f"/api/runs/{body['run_id']}/resume", json={"decisions": {pending_job_id: "queue"}}
    )
    assert run_calls == [
        NotificationKind.HUMAN_INTERVENTION_REQUIRED,
        NotificationKind.RUN_COMPLETED,
    ]


async def test_application_notifies_human_review_then_submitted(client, monkeypatch):
    app_calls = _patch_notify(monkeypatch, "app.graph.apply_service")
    await _seed_profile(with_name_and_phone=True)
    job = make_job()

    create_response = await client.post(
        "/api/applications",
        json={
            "job": job.model_dump(mode="json"),
            "form_page_url": _fixture_url("simple_application_form.html"),
        },
    )
    application_id = create_response.json()["application_id"]
    assert app_calls == [NotificationKind.HUMAN_INTERVENTION_REQUIRED]

    resume_response = await client.post(
        f"/api/applications/{application_id}/resume", json={"payload": {"approved": True}}
    )
    assert resume_response.json()["application_status"] == "dry_run_ready"
    assert app_calls == [
        NotificationKind.HUMAN_INTERVENTION_REQUIRED,
        NotificationKind.APPLICATION_SUBMITTED,
    ]


async def test_application_rejection_sends_no_final_notification(client, monkeypatch):
    app_calls = _patch_notify(monkeypatch, "app.graph.apply_service")
    await _seed_profile(with_name_and_phone=True)
    job = make_job()

    create_response = await client.post(
        "/api/applications",
        json={
            "job": job.model_dump(mode="json"),
            "form_page_url": _fixture_url("simple_application_form.html"),
        },
    )
    application_id = create_response.json()["application_id"]

    resume_response = await client.post(
        f"/api/applications/{application_id}/resume", json={"payload": {"approved": False}}
    )
    assert resume_response.json()["application_status"] == "rejected_by_human"
    # Only the initial human-review notification — no notification is
    # sent for a human's own rejection decision.
    assert app_calls == [NotificationKind.HUMAN_INTERVENTION_REQUIRED]

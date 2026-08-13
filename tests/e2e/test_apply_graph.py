"""End-to-end tests for the apply subgraph (Section 19, Phase 6) — real
Playwright, real local HTML fixtures, real LangGraph checkpointing.
"""

from __future__ import annotations

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.graph import apply_service
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction
from tests.e2e.conftest import fixture_url
from tests.fixtures.job_builder import make_job


async def _seed_profile(*, email: str | None = "jordan@example.com") -> None:
    resume = ResumeExtraction(
        source_file="resume.pdf",
        raw_text="...",
        email=(
            ExtractedField[str](value=email, source="resume", confidence=0.95)
            if email
            else ExtractedField[str].unextracted()
        ),
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


async def test_unknown_field_interrupt_then_approval_flow():
    await _seed_profile()
    job = make_job()

    started = await apply_service.start_application(
        job, form_page_url=fixture_url("unknown_field_form.html")
    )
    assert started is not None
    assert started.status == "waiting_human"
    assert started.interrupt["reason"] == "UNKNOWN_REQUIRED_FIELD"
    unknown_fields = {f["field"] for f in started.interrupt["fields"]}
    assert "fav_language" in unknown_fields

    after_field_answer = await apply_service.resume_application(
        started.application_id, {"fav_language": "Python"}
    )
    assert after_field_answer is not None
    assert after_field_answer.status == "waiting_human"
    assert after_field_answer.interrupt["reason"] == "MANUAL_APPROVAL_REQUIRED"

    final = await apply_service.resume_application(started.application_id, {"approved": True})
    assert final is not None
    assert final.status == "completed"
    # AUTOMATION_DRY_RUN defaults to true — must never actually submit.
    assert final.application_status == "dry_run_ready"


async def test_otp_interrupt_flow():
    await _seed_profile()
    job = make_job()

    started = await apply_service.start_application(
        job,
        form_page_url=fixture_url("simple_application_form.html"),
        challenge_page_urls=[fixture_url("otp_screen.html")],
    )
    assert started is not None
    assert started.status == "waiting_human"
    assert started.interrupt["reason"] == "OTP_REQUIRED"

    after_otp = await apply_service.resume_application(
        started.application_id, {"otp_code": "123456"}
    )
    assert after_otp is not None
    assert after_otp.status == "waiting_human"
    assert after_otp.interrupt["reason"] == "MANUAL_APPROVAL_REQUIRED"

    final = await apply_service.resume_application(started.application_id, {"approved": True})
    assert final is not None
    assert final.application_status == "dry_run_ready"


async def test_captcha_interrupt_flow():
    await _seed_profile()
    job = make_job()

    started = await apply_service.start_application(
        job,
        form_page_url=fixture_url("simple_application_form.html"),
        challenge_page_urls=[fixture_url("captcha_screen.html")],
    )
    assert started is not None
    assert started.interrupt["reason"] == "CAPTCHA_REQUIRED"

    after_captcha = await apply_service.resume_application(started.application_id, {"solved": True})
    assert after_captcha is not None
    assert after_captcha.interrupt["reason"] == "MANUAL_APPROVAL_REQUIRED"

    final = await apply_service.resume_application(started.application_id, {"approved": True})
    assert final is not None
    assert final.application_status == "dry_run_ready"


async def test_manual_approval_rejection_produces_rejected_status():
    await _seed_profile()
    job = make_job()

    started = await apply_service.start_application(
        job, form_page_url=fixture_url("simple_application_form.html")
    )
    assert started is not None
    assert started.interrupt["reason"] == "MANUAL_APPROVAL_REQUIRED"

    final = await apply_service.resume_application(started.application_id, {"approved": False})
    assert final is not None
    assert final.status == "completed"
    assert final.application_status == "rejected_by_human"


async def test_get_application_state_reflects_paused_and_completed():
    await _seed_profile()
    job = make_job()

    started = await apply_service.start_application(
        job, form_page_url=fixture_url("simple_application_form.html")
    )
    assert started is not None

    paused_state = await apply_service.get_application_state(started.application_id)
    assert paused_state is not None
    assert paused_state.status == "waiting_human"
    assert paused_state.interrupt == started.interrupt

    final = await apply_service.resume_application(started.application_id, {"approved": True})
    assert final is not None

    completed_state = await apply_service.get_application_state(started.application_id)
    assert completed_state is not None
    assert completed_state.status == "completed"
    assert completed_state.application_status == final.application_status


async def test_unknown_application_id_returns_none():
    assert await apply_service.get_application_state("does-not-exist") is None
    assert await apply_service.resume_application("does-not-exist", {}) is None


async def test_starting_without_a_candidate_profile_returns_none():
    job = make_job()
    result = await apply_service.start_application(
        job, form_page_url=fixture_url("simple_application_form.html")
    )
    assert result is None

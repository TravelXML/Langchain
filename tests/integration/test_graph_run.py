from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.graph import service
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction

# Tuned (see the module-level comment in app/graph/mock_portals.py for the
# fixture data) so that, against the mock jobs, exactly one job — "Head of
# Engineering" at Gamma Systems — lands in the human_review band. This is
# what lets these tests exercise the interrupt/resume path deterministically
# rather than only the happy path.
#
# work_authorization is set explicitly so these Phase 3 (score-routing)
# tests aren't also exercising the Phase 4 guardrail that flags an unset
# work_authorization as HUMAN_INPUT_REQUIRED for every job — that path has
# its own tests in test_guardrails_graph_integration.py.
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


async def _seed_profile(session: AsyncSession, *, experience_years: float | None = 15.0) -> None:
    resume = ResumeExtraction(
        source_file="resume.pdf",
        raw_text="...",
        email=ExtractedField[str](value="jordan@example.com", source="resume", confidence=0.95),
        experience_years=(
            ExtractedField[float](value=experience_years, source="resume", confidence=0.7)
            if experience_years is not None
            else ExtractedField[float].unextracted()
        ),
    )
    record = CandidateProfileRecord(
        id=DEFAULT_PROFILE_ID,
        preferences=_PREFERENCES.model_dump(mode="json"),
        resume=resume.model_dump(mode="json"),
    )
    session.add(record)
    await session.commit()


async def _seed_default_profile() -> None:
    async with get_sessionmaker()() as session:
        await _seed_profile(session)


async def test_run_pauses_for_human_review_then_resumes_with_queue_decision():
    await _seed_default_profile()

    started = await service.start_run()
    assert started.status == "waiting_human"
    assert started.interrupt is not None
    assert started.interrupt["reason"] == "HUMAN_REVIEW_REQUIRED"
    pending_titles = [j["title"] for j in started.interrupt["jobs"]]
    assert pending_titles == ["Head of Engineering"]

    pending_job_id = started.interrupt["jobs"][0]["job_id"]
    resumed = await service.resume_run(started.run_id, {pending_job_id: "queue"})

    assert resumed.status == "completed"
    assert resumed.metrics is not None
    assert resumed.metrics["duplicates"] == 1  # Acme SaaS CTO posted on both mock portals
    queued_titles = {j.title for j in resumed.queued}
    assert "CTO" in queued_titles
    assert "Head of Engineering" in queued_titles
    assert all(j.recommendation != "reject" for j in resumed.queued)


async def test_resume_with_reject_decision_moves_job_to_rejected():
    await _seed_default_profile()

    started = await service.start_run()
    pending_job_id = started.interrupt["jobs"][0]["job_id"]

    resumed = await service.resume_run(started.run_id, {pending_job_id: "reject"})

    assert resumed.status == "completed"
    rejected_titles = {j.title for j in resumed.rejected}
    assert "Head of Engineering" in rejected_titles
    queued_titles = {j.title for j in resumed.queued}
    assert "Head of Engineering" not in queued_titles


async def test_get_run_state_reflects_paused_run():
    await _seed_default_profile()

    started = await service.start_run()
    state = await service.get_run_state(started.run_id)

    assert state is not None
    assert state.status == "waiting_human"
    assert state.interrupt == started.interrupt


async def test_get_run_state_reflects_completed_run():
    await _seed_default_profile()

    started = await service.start_run()
    pending_job_id = started.interrupt["jobs"][0]["job_id"]
    resumed = await service.resume_run(started.run_id, {pending_job_id: "queue"})

    state = await service.get_run_state(started.run_id)
    assert state is not None
    assert state.status == "completed"
    assert state.metrics == resumed.metrics


async def test_unknown_run_id_returns_none():
    assert await service.get_run_state("does-not-exist") is None
    assert await service.resume_run("does-not-exist", {}) is None


async def test_run_without_candidate_profile_produces_no_jobs_and_no_interrupt():
    # No profile seeded — load_candidate_profile_node should surface an
    # error rather than crash, and scoring should simply produce nothing.
    result = await service.start_run()
    assert result.status == "completed"
    assert result.queued == []
    assert result.errors

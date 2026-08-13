"""Proves the Phase 4 guardrail engine is actually wired into policy_guard
(app/graph/nodes.py), not just a standalone library exercised by
test_guardrails.py's unit tests.
"""

from __future__ import annotations

from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.graph import service
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction

_BASE_PREFERENCES = dict(
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


async def _seed_profile(preferences: CandidatePreferences) -> None:
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
                preferences=preferences.model_dump(mode="json"),
                resume=resume.model_dump(mode="json"),
            )
        )
        await session.commit()


async def test_excluded_company_rejects_a_job_the_scorer_would_have_queued():
    # "CTO" at Acme SaaS is the best-scoring mock job (see mock_portals.py)
    # and would normally queue outright — excluding the company must
    # override that.
    preferences = CandidatePreferences(**{**_BASE_PREFERENCES, "companies_exclude": ["Acme SaaS"]})
    await _seed_profile(preferences)

    started = await service.start_run()
    # Head of Engineering still needs a human decision on its own merits.
    resumed = await service.resume_run(
        started.run_id, {started.interrupt["jobs"][0]["job_id"]: "queue"}
    )

    assert resumed.status == "completed"
    assert "CTO" not in {j.title for j in resumed.queued}
    rejected_cto = next(j for j in resumed.rejected if j.title == "CTO")
    assert "excluded" in rejected_cto.reason.lower()
    assert rejected_cto.recommendation == "reject"


async def test_unknown_work_authorization_pauses_run_for_an_otherwise_auto_queued_job():
    preferences = CandidatePreferences(**{**_BASE_PREFERENCES, "work_authorization": None})
    await _seed_profile(preferences)

    started = await service.start_run()

    assert started.status == "waiting_human"
    pending_titles = {j["title"] for j in started.interrupt["jobs"]}
    # CTO would have auto-queued on score alone (Phase 3 behavior) — the
    # guardrail must still pull it into human review.
    assert "CTO" in pending_titles
    cto_entry = next(j for j in started.interrupt["jobs"] if j["title"] == "CTO")
    assert "work" in cto_entry["note"].lower()

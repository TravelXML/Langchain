# Job Automation Platform

A local-first, multi-agent job discovery, matching, application-preparation,
and application-automation platform. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for system design and [`SECURITY.md`](SECURITY.md) for the safety model.

Runs primarily on your machine, uses a local LLM (Ollama) by default, and
requires no paid API key for the basic install.

## Status

- **Phase 0 — Project Bootstrap**: repository skeleton, FastAPI app,
  structured logging, configuration system, async database foundation +
  Alembic, `/health`.
- **Phase 1 — Candidate Profile**: resume/cover-letter PDF ingestion,
  deterministic (non-LLM) structured extraction, `candidate_profiles` table,
  `/api/profile` (`GET`, `POST /import`, `PUT`).
- **Phase 2 — Job Model + Matching Engine**: `NormalizedJob` + portal-agnostic
  `normalize_job()`, and a fully rule-based weighted scorer
  (`app/matching/`) covering title/seniority, skills (with alias
  normalization), experience, salary, location, and industry — configurable
  via `config/scoring.yaml`, no LLM or API involved.
- **Phase 3 — LangGraph Core**: the supervisor graph (`app/graph/`) —
  discover (parallel, mocked portals) → normalize → dedupe → score → policy
  guard → finalize, with a real human-in-the-loop interrupt (jobs scoring in
  the `human_review` band pause the run) and SQLite-backed checkpointing so
  a run survives a process restart. Exposed via `/api/runs`.
- **Phase 4 — Guardrails**: a deterministic policy engine (`app/guardrails/`,
  12 checks — score floor, daily/per-company limits, excluded companies/
  roles/locations, salary floor, experience mismatch, work authorization,
  duplicate detection, resume/identity completeness) wired into `policy_guard`
  with final say over the scorer — it can only make a job *more* restricted
  (queue → human_review → reject), never less.
- **Phase 5 — Playwright Form Engine**: real browser automation
  (`app/browser/`) against **local HTML fixtures only** — field detection
  (single DOM-walk JS scan), a deterministic (non-LLM) field-to-candidate
  mapping with an honest `requires_human` flag, filling (text/select/
  checkbox/file upload), HTML5 validation, multi-step navigation, and
  screenshot + HTML-snapshot capture on failure.
- **Phase 6 — Human Interrupt**: a standalone "apply" subgraph
  (`app/graph/apply_*.py`) that wires Phase 5's form engine into four real
  `interrupt()` pause points — an unrecognized/low-confidence field, an
  OTP screen, a CAPTCHA screen, and manual approval before "submission" —
  each resolved via `POST /api/applications/{id}/resume` and checkpointed
  the same way as Phase 3's discovery interrupt. `AUTOMATION_DRY_RUN=true`
  is enforced at the very last step regardless of approval. Exposed via
  `/api/applications`.

Everything else described in the architecture doc (a real portal adapter,
dashboard, scheduler) lands in later phases.

## Quickstart

```bash
git clone <repo-url>
cd job-automation

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium   # required from Phase 5 on (app/browser/, e2e tests)

cp .env.example .env
alembic upgrade head          # creates ./data/job_automation.db with the current schema

# run the API
uvicorn app.main:app --reload
# in another shell:
curl http://localhost:8000/health
```

Or via the Makefile:

```bash
make install
make dev     # runs the API with reload
make test    # runs the test suite
```

### Importing your resume

```bash
curl -X POST http://localhost:8000/api/profile/import \
  -F "resume=@/path/to/resume.pdf;type=application/pdf" \
  -F "cover_letter=@/path/to/cover_letter.pdf;type=application/pdf"   # optional

curl http://localhost:8000/api/profile
```

Extraction in Phase 1 is deliberately **rule-based, not LLM-based** — resume
"understanding" is an LLM task per the design spec, and no LLM is wired up
yet (LLM integration isn't gated behind a specific numbered phase — see
Sections 36-39). So today's extractor pulls what regex/section-scanning can
get honestly (email, phone, a name guess, years of experience, skills
matched against a vocabulary, and labeled sections like education/
certifications) and leaves everything else — previous titles, companies,
industries — as `{"value": null, "confidence": 0.0, "source": "unextracted"}`
rather than guessing. See `app/profile/parser.py` and Section 6/17 of the
architecture spec ("never invent information missing from the resume").

### Scoring a job against the candidate

For a single job outside a full run, scoring is a direct library call —
`app.jobs.parser.normalize_job()` turns a raw job dict into a
`NormalizedJob`, and `app.matching.scorer.score_job()` scores it against
`CandidatePreferences` + resume skills/experience. (For the full discovery
pipeline, see [Running a discovery pipeline](#running-a-discovery-pipeline)
below.)

```python
from app.jobs.parser import normalize_job
from app.matching.scorer import score_job
from app.profile.models import CandidatePreferences

job = normalize_job(
    {
        "url": "https://boards.greenhouse.io/acme/jobs/4821",
        "title": "Chief Technology Officer",
        "company": "Acme TravelTech",
        "location": "Bengaluru, India",
        "work_mode": "hybrid",
        "salary_min": 45, "salary_max": 65, "salary_currency": "INR",
        "required_skills": ["Cloud Architecture", "Engineering Leadership", "AWS"],
        "preferred_skills": ["Agentic AI", "Kubernetes"],
        "minimum_experience": 15,
        "industry": "TravelTech",
    },
    source="greenhouse",
)

result = score_job(
    job,
    preferences=CandidatePreferences(
        target_positions=["CTO", "VP Technology"],
        preferred_industries=["TravelTech", "SaaS"],
        locations_preferred=["Bengaluru", "Remote"],
        relocation_allowed=True,
        work_mode=["remote", "hybrid"],
        compensation_currency="INR", compensation_minimum=30, compensation_preferred=50,
    ),
    candidate_skills=["Cloud Architecture", "Engineering Leadership", "Amazon Web Services", "Agentic AI"],
    candidate_experience_years=20,
)
# result.overall_score == 95.5, result.recommendation == "priority_apply"
# "Amazon Web Services" was recognized as "AWS" via alias normalization.
```

Scoring is entirely deterministic — no LLM, no embeddings (Section 16/38
add those as an *additional* signal in a later phase; the rule-based score
is never replaced by them). Weights and thresholds come from
`config/scoring.yaml`.

### Running a discovery pipeline

With a candidate profile imported (see above), `POST /api/runs` drives the
full supervisor graph: discover jobs from every enabled portal in parallel
→ normalize → cross-portal dedupe → score → route to queue/reject/human
review → finalize. Portal adapters don't exist yet (Phase 7), so discovery
currently uses two mock portals (`app/graph/mock_portals.py`) with data
tuned to exercise every path, including a deliberate cross-portal duplicate.

```bash
curl -X POST http://localhost:8000/api/runs
```

If any job's score lands in the `human_review` band (60–74), **or** the
Phase 4 guardrail engine flags something a score alone can't tell you
(unknown work authorization, an excluded company, a duplicate application,
...), the run **pauses** — the response comes back with `status:
"waiting_human"` and the pending job(s) needing a decision. Guardrails run
*after* scoring and can only tighten the outcome (queue → human_review →
reject), never loosen it — a `priority_apply`-scored job from an excluded
company still ends up rejected. Note in particular: `work_authorization` is
unset by default (`config/candidate.yaml`), so a fresh install will pause
on every job until you set it — that's intentional (Section 18: never
guessed).

```json
{
  "run_id": "6b9e4e2c-...",
  "status": "waiting_human",
  "interrupt": {
    "reason": "HUMAN_REVIEW_REQUIRED",
    "jobs": [{"job_id": "f5eafa7a-...", "title": "Head of Engineering", "company": "Gamma Systems", "score": 66.0, "note": "... | guardrails: candidate has not stated a work-authorization status"}]
  }
}
```

Resolve it (`"queue"` or `"reject"` per job id) to resume:

```bash
curl -X POST http://localhost:8000/api/runs/<run_id>/resume \
  -H "Content-Type: application/json" \
  -d '{"decisions": {"f5eafa7a-...": "queue"}}'
```

The paused state is checkpointed to `LANGGRAPH_CHECKPOINT_PATH`
(`./data/langgraph_checkpoints.db` by default) — killing the server between
the pause and the resume and starting a fresh process still resumes
correctly (verified manually; see `app/graph/graph.py`'s docstring). Check
status any time with `GET /api/runs/<run_id>`.

### Trying the form engine

Used directly as a library — for the version wired into a full apply
flow with interrupts, see [Trying the apply flow](#trying-the-apply-flow)
below:

```python
import asyncio
from pathlib import Path

from app.browser.manager import launch_browser
from app.browser.forms import detect_fields, fill_form, validate_form
from app.browser.mapping import map_fields
from app.profile.models import CandidateProfile  # ... build or load one

async def main():
    profile = ...  # e.g. app.profile.profile_service.get_profile(session)
    fixture = Path("tests/fixtures/html/simple_application_form.html").resolve()

    async with launch_browser() as browser:
        page = await browser.new_page()
        await page.goto(f"file://{fixture}")

        fields = await detect_fields(page)
        mappings = map_fields(fields, profile)   # each has candidate_value/confidence/requires_human
        result = await fill_form(page, fields, mappings)
        print("filled:", result.filled, "needs a human:", result.skipped_for_human)

        assert await validate_form(page) == []   # no missing required fields
        await page.click('[data-testid="submit-button"]')

asyncio.run(main())
```

A field the mapper isn't confident about (or has no known pattern for —
see the sensitive categories in `app/browser/mapping.py`) is never guessed:
it comes back with `candidate_value=None, requires_human=True` and
`fill_form` leaves it untouched rather than filling something wrong.

### Trying the apply flow

`POST /api/applications` runs one job through the full apply subgraph —
detect/map fields → fill/validate → pass any OTP/CAPTCHA challenge pages →
manual approval → finalize — pausing for a human at four different points
along the way (Section 19). No portal adapter exists yet (Phase 7), so
`form_page_url`/`challenge_page_urls` point at local fixtures:

```bash
curl -X POST http://localhost:8000/api/applications \
  -H "Content-Type: application/json" \
  -d '{
    "job": {"id": "job-1", "source": "demo", "url": "https://example.com/1",
            "title": "CTO", "company": "Acme SaaS", "discovered_at": "2026-08-13T00:00:00Z",
            "required_skills": [], "preferred_skills": [], "metadata": {}},
    "form_page_url": "file:///.../tests/fixtures/html/simple_application_form.html",
    "challenge_page_urls": ["file:///.../tests/fixtures/html/otp_screen.html"]
  }'
```

The response pauses with `status: "waiting_human"` and an `interrupt`
whose `reason` is one of:

- `UNKNOWN_REQUIRED_FIELD` — a field the mapper wasn't confident about;
  resolve with `{"payload": {"<field name>": "<answer>"}}`
- `OTP_REQUIRED` — resolve with `{"payload": {"otp_code": "123456"}}`
- `CAPTCHA_REQUIRED` — resolve with `{"payload": {"solved": true}}`
  (the system never attempts to solve it itself — Section 12)
- `MANUAL_APPROVAL_REQUIRED` — always fires last (the default
  `approval.mode: manual`, Section 48), showing every field about to be
  submitted; resolve with `{"payload": {"approved": true}}` or `false`

```bash
curl -X POST http://localhost:8000/api/applications/<id>/resume \
  -H "Content-Type: application/json" \
  -d '{"payload": {"otp_code": "123456"}}'
```

A completed run's `application_status` is `dry_run_ready` (the
`AUTOMATION_DRY_RUN=true` default — nothing is ever actually submitted,
even after approval, since there's no real portal to submit to yet) or
`rejected_by_human` if the final approval was declined. Verified manually
with a genuine process restart between the `OTP_REQUIRED` pause and its
resume — same persistence guarantee as Phase 3's discovery interrupt.

## Local LLM setup (Ollama)

The platform defaults to a local Ollama instance and never requires a paid
API key. Not wired up yet — no phase has needed an LLM so far (Sections
2/17 push everything possible to deterministic code first); for now
`config/llm.yaml` and `.env.example` document the expected configuration:

```bash
# install Ollama separately: https://ollama.com
ollama pull <your-chosen-model>
export OLLAMA_MODEL=<your-chosen-model>
```

No specific model is hardcoded anywhere in the codebase — set `OLLAMA_MODEL`
to whatever you have pulled locally.

## Configuration

- `.env` — machine-specific settings and secrets (never committed; see
  `.env.example`).
- `config/*.yaml` — domain configuration (candidate preferences, scoring
  weights, search policy, automation limits, portal registry). Intended to
  be editable from the future dashboard without code changes.

## Safety defaults

Two defaults are intentionally conservative and must be changed explicitly:

- `automation.dry_run: true` — no application is ever submitted until you
  turn this off.
- `approval.mode: manual` — every application requires human approval until
  you opt into `hybrid` or `automatic`.

See [`SECURITY.md`](SECURITY.md) for the full safety model.

## Repository layout

```text
app/
  core/            configuration, logging
  api/              FastAPI routes (health, profile, runs, applications)
  database/         async SQLAlchemy session/models
  profile/           candidate profile parsing — loader/parser/services (Phase 1)
  jobs/              NormalizedJob + portal-agnostic normalize_job() (Phase 2)
  matching/          job-candidate scoring engine — title/skills/experience/
                      salary/location/industry, all rule-based (Phase 2)
  graph/             LangGraph supervisor (state/nodes/graph/service,
                      mocked portals until Phase 7 — Phase 3) + the apply
                      subgraph (apply_state/apply_nodes/apply_graph/
                      apply_service — Phase 6)
  agents/            LLM-driven agent steps (empty until the LLM
                      integration phase)
  guardrails/        deterministic policy engine — models/policy/engine,
                      12 checks, wired into graph/nodes.py's policy_guard (Phase 4)
  browser/           Playwright automation — manager/sessions/selectors/
                      forms/mapping/detection/screenshots/errors (Phase 5-6)
  portals/           portal adapters (Phase 7+)
  llm/               local LLM provider abstraction (not yet built)
  observability/ notifications/ scheduler/ security/
config/              YAML domain configuration
prompts/             versioned LLM prompts (not yet used — no LLM wired up yet)
tests/               unit / integration / e2e / fixtures / mocks
migrations/           Alembic migrations
```

## Development

```bash
make lint       # ruff
make format     # black
make typecheck  # mypy
make test       # pytest
```

## Notes for contributors

- **`get_engine()`/`get_sessionmaker()` take no arguments.** They resolve
  settings via the `get_settings()` singleton internally. Don't add an
  optional `settings` parameter back in: `functools.lru_cache` keys strictly
  on what a call site passes, so `get_engine()` vs. `get_engine(None)` (or
  `get_engine(some_settings)`) hash to *different* cache entries and quietly
  produce two unrelated engines. Harmless for file-based SQLite/Postgres
  (both point at the same backing store); fatal for in-memory SQLite, where
  each engine is a wholly separate database. This bit Phase 1's profile API
  tests — the fix is in `app/database/session.py`.
- **A fresh `./data/job_automation.db` needs `alembic upgrade head`** before
  the API can serve anything beyond `/health` — tests don't need this (an
  autouse fixture creates tables against the in-memory test DB directly) but
  real local runs do.
- **LangGraph node functions must name their state parameter `state`.**
  mypy's stubs for `StateGraph.add_node` structurally match your function
  against an internal `_Node` protocol, and — surprisingly — that match
  fails if you name an unused parameter `_state` (the usual Python
  convention for "unused"). Two nodes in `app/graph/nodes.py` hit this
  during Phase 3; renaming to `state` (even though it's unused in those two)
  fixed it with no `type: ignore` needed. If you add a node and see a wall
  of `add_node` overload errors, check the parameter name first.
- **The LangGraph checkpoint DB (`LANGGRAPH_CHECKPOINT_PATH`) must be a real
  file, not `:memory:`, outside of single-process test runs.**
  `app/graph/graph.py`'s `compiled_graph()` opens a fresh sqlite connection
  per call (deliberately, to prove state survives process restarts, per
  Section 26) — an in-memory DB would be empty on every new connection.
  Tests point it at a temp file for the same reason the main app DB can use
  `:memory:` (a cached, single, StaticPool-backed engine) while this can't.
- **`check_minimum_score` (Phase 4) deliberately skips jobs the scorer
  already routed to `human_review`.** The candidate's personal
  `minimum_match_score` (`config/candidate.yaml`, default 75) and the
  scorer's own `human_review` threshold (`config/scoring.yaml`, default 60)
  are two independent, differently-scoped numbers — without the carve-out, a
  stricter personal minimum would silently reject a job before a human ever
  saw it, defeating the interrupt that Phase 3 built. See
  `app/guardrails/policy.py::check_minimum_score`'s docstring.
- **Test fixtures for a `CandidateProfile` need `resume.email` set, not just
  `experience_years`.** Phase 4's `check_mandatory_fields` guardrail blocks
  any application with no email on file — realistic (a real parsed resume
  always has one), but it silently swallowed several Phase 3 tests' human-
  review scenarios when the fixture resume only set `experience_years`. If a
  graph-integration test unexpectedly completes instead of pausing, check
  the seeded resume has an email first.
- **`CandidatePreferences.work_authorization` defaults to `None`**, and the
  guardrail for it fires for *every* job when unset (Section 18: never
  guessed). Test fixtures that aren't specifically testing that guardrail
  should set it explicitly (e.g. `work_authorization="citizen"`) or every
  job will end up in `human_review`.
- **Playwright's `select_option(label=...)` requires an exact string
  match, including case.** `config/candidate.yaml` stores `work_mode`
  lowercase (`remote`); a real portal's `<option>` text is often
  capitalized (`Remote`). `app/browser/forms.py::_select_option_case_insensitive`
  retries with a case-insensitive lookup before giving up — if you add
  another `<select>`-handling path, route it through that helper rather
  than calling `select_option` directly, or a confidently-mapped field
  will fail to fill over nothing but casing.

## Development workflow

This project is built in explicit phases (see the architecture doc's
implementation plan). Each phase stops for review before the next begins —
the repository will not contain portal automation, browser automation, or
LLM integration until those phases are explicitly implemented.

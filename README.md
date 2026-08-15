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
- **Phase 7 — First Portal Adapter**: `app/portals/base` (the
  `JobPortalAdapter` interface, Section 9) and `app/portals/greenhouse`,
  the first real (non-mock) adapter — discovery and job detail-loading via
  Greenhouse's real public Job Board API, application handling delegated
  to the same browser engine Phases 5-6 already built. Verified live
  against GitLab's actual careers board (201 real jobs; real read-only
  field detection against a real live application page — see
  [Trying the Greenhouse adapter](#trying-the-greenhouse-adapter)).
  Config-gated and off by default (`config/portals.yaml`'s
  `greenhouse.boards` ships empty) — a fresh install still runs entirely
  against the local mock portals until you add a board token.

- **Phase 8 — Dashboard**: a real persistence layer (`jobs`, `applications`,
  `automation_runs`, `human_interventions` tables, written at the service
  layer right after Phases 3/6's graphs return, alongside — not instead of —
  their existing LangGraph checkpointers) plus the API surface it enables
  (`GET /api/jobs`, `GET /api/jobs/{id}`, `GET /api/applications`,
  `GET /api/runs`, `GET /api/human-actions` +
  `POST /api/human-actions/{id}/resolve` as a unified queue over both
  Phase 3's and Phase 6's interrupts, `GET /api/analytics/summary`,
  `GET`/`PUT /api/settings`) and a Vite + React + TypeScript + Recharts
  frontend (`frontend/`) with six pages: Overview, Jobs, Job detail
  (score breakdown), Applications, Human Review (resolves every interrupt
  reason inline), and Analytics. Verified live end-to-end — a real
  discovery run, a real multi-interrupt application (unknown field →
  manual approval) resolved through the actual UI, screenshotted at every
  step (see [Running the dashboard](#running-the-dashboard)).

- **Phase 9 — Scheduler + Notifications**: a process-wide APScheduler
  instance (`app/scheduler/`), independent from LangGraph — every
  scheduled job calls `graph.service.start_run()`, the same entrypoint
  `POST /api/runs` uses, with no knowledge of graph internals. Cron and
  interval schedules come from `config/automation.yaml`'s `scheduler`
  section (disabled by default) and a daily-summary job registers
  automatically whenever it's enabled. A pluggable notification
  abstraction (`app/notifications/`, `NotificationProvider`) ships four
  implementations — Console (on by default, zero setup), Webhook, Email
  (stdlib `smtplib`, no new dependency), Desktop (`notify-send`, no-ops
  where unavailable) — fired on run completed/failed, application
  submitted/failed, human intervention required, and the daily summary.
  Both are editable live via `PUT /api/settings` (a `scheduler` edit
  triggers an immediate reload, no restart). Verified live: a real
  25-second interval schedule firing two real discovery runs in a row,
  console + webhook notifications actually delivered (a local HTTP
  receiver captured the real POST bodies), and a live Settings edit
  disabling the scheduler mid-run (see
  [Trying the scheduler and notifications](#trying-the-scheduler-and-notifications)).
- **Phase 10 — Additional Portals**: `app/portals/lever/`, the second
  real (non-mock) adapter, via Lever's real public Postings API
  (`api.lever.co/v0/postings/<company>`) — same "official/public API, no
  scraping, no auth" pattern as Greenhouse. Adding it did **not** touch
  `app/graph/nodes.py`: Phase 7 had actually hardcoded a
  `portal.startswith("greenhouse:")` branch directly in the supervisor,
  which is exactly what Phase 10 rules out repeating ("do not modify the
  supervisor for every new portal") — so this phase first pulled that
  into a generic `app/portals/registry.py` that both adapters (and any
  future one) plug into, then added Lever through it with zero further
  `nodes.py` changes. Config-gated and off by default
  (`config/portals.yaml`'s `lever.companies` ships empty), same as
  Greenhouse. Verified live against Lever's own public demo board
  (`leverdemo`): 388 real postings discovered, and — the important
  part — real field detection + mapping against Lever's actual
  application page found 50 real fields (including a rich set of EEO/
  demographic questions: gender, race/ethnicity, veteran status,
  disability status, pronouns), with only name/email/phone auto-mapped
  and all 46 sensitive/unrecognized fields correctly left for a human
  (see [Trying the Lever adapter](#trying-the-lever-adapter)).

Workday, LinkedIn, Naukri, and Indeed remain unimplemented — none expose
a comparable official, unauthenticated, scrape-free public API the way
Greenhouse and Lever do, and Section 12 ("prefer official/public APIs...
respect portal terms") rules out reaching for scraping or login-bypassing
automation to fill that gap.

- **LLM Integration (Sections 36-39)**: never gated behind a numbered
  phase in the original spec, built after Phase 10. `app/llm/` — a
  provider abstraction, a real `OllamaProvider` (structured JSON output
  validated against Pydantic schemas, never a bare dict), capability-
  based model routing (`router.py`, every capability defaults to the
  same model today), an embedding provider with in-process caching
  (`embeddings.py`), a versioned prompt loader (`prompts.py`) plus seven
  real prompt templates under `prompts/`, and startup health checks
  (`health.py`) wired into `app.main`'s lifespan — failing gracefully
  (logged, never raised) rather than crashing the app when Ollama isn't
  reachable. **No real Ollama instance was available in this
  development session**, so every `app/llm/` test mocks the HTTP layer;
  the one thing verified against real conditions is the app's actual
  startup behavior with Ollama genuinely absent
  (`tests/integration/test_app_startup.py`), not a simulated absence.
  Nothing in the scoring/matching/extraction path calls into this yet —
  a deliberate scoping decision, see
  [Local LLM setup (Ollama)](#local-llm-setup-ollama) for why.

- **CLI (Section 46)**: `jobagent` — a thin operator-facing wrapper over
  the exact same domain services `app/api/routes/` calls (no logic
  duplicated), installed as a console script (`app/cli/main.py`, Typer).
  `jobagent profile import/show`, `run`, `applications list`,
  `human pending`/`resolve`, and `doctor` (Python version, database,
  Playwright browser, Ollama, configured LLM, resume files, environment,
  required directories — never fails the command itself, only reports).
  See [Using the CLI](#using-the-cli). Building this surfaced two real
  bugs in `app/core/logging.py`, both fixed: logs defaulted to stdout
  with no way to separate them from a command's actual JSON output, and
  `cache_logger_on_first_use=True` meant a second `configure_logging()`
  call in the same process (which the CLI does by design, once per
  invocation) could leave an unrelated module-level logger holding a
  stale, closed-stream reference — a latent bug the CLI's tests exposed,
  not something specific to the CLI itself.

- **Central Error Handling (Section 40)**: `app/browser/errors.py`'s
  Phase 5 docstring promised "full portal/application exceptions land
  in Phase 7" — Phase 7 shipped Greenhouse without them, a gap this
  closes. `app/core/errors.py`'s `JobAutomationError` is now the shared
  base every exception in the codebase (browser-, LLM-, and portal-
  level) inherits from, capturing url/portal/job_id/run_id/
  screenshot_path/step/timestamp uniformly via `.to_dict()` —
  deliberately never a credential: captured URLs have their query
  string stripped specifically because that's the most common place a
  secret accidentally leaks into one. `app/portals/errors.py` adds
  `PortalAuthenticationError`/`PortalNavigationError`/`RateLimitError`,
  wired into `app/portals/http.py` (one shared httpx-error translator
  both Greenhouse's and Lever's clients route through — a 429 becomes
  `RateLimitError`, anything else non-2xx or unreachable becomes
  `PortalNavigationError`), verified live against both real APIs with
  an invalid board/company. `DuplicateApplicationError` closes a real,
  previously-unguarded gap: `apply_service.start_application` now
  checks for an existing application on the same job first (Section 50:
  "before submitting, check existing application") rather than silently
  creating a second one — verified live via two real API calls for the
  same job, the second correctly rejected with `409`.
  `ApplicationValidationError`/`SubmissionVerificationError`/
  `HumanActionRequired` are defined but not raised anywhere yet, each
  documented with exactly why (the graph's own `interrupt()`/warning-
  based design already covers what they'd otherwise be for).

- **Hybrid Approval Mode (Section 48)**: `apply_nodes.py`'s
  `manual_approval_node` docstring explicitly flagged this as
  unimplemented since Phase 6 ("Phase 6 doesn't yet implement hybrid's
  score/confidence auto-approval carve-out"). It's implemented now:
  `hybrid` mode auto-approves only when a job's match score *and* every
  auto-filled field's confidence both clear configurable bars
  (`config/automation.yaml`'s `approval.hybrid_min_score`/
  `hybrid_min_confidence`, defaulting to 90 and 0.85) *and* no field was
  left `requires_human` — otherwise it falls through to the exact same
  manual-review interrupt `manual` mode uses. A missing match score
  (the apply graph doesn't compute one itself — it's an optional
  parameter a caller supplies) never auto-approves, matching Section
  17's "never guessed." Verified live: a real high-score, fully-
  auto-mapped application completed immediately with no pause at all;
  the same job with no score supplied correctly paused for manual
  review instead.
- **Docker Compose frontend service (Section 45)**: `frontend/`
  (Phase 8) had no Dockerfile and `docker-compose.yml` had no `frontend`
  service — `docker compose up` never actually launched the dashboard.
  `frontend/Dockerfile` is a standard two-stage build (Node builds the
  static assets, nginx serves them); `VITE_API_BASE_URL` is a build arg
  since Vite bakes env vars in at build time, not runtime, and it must
  be a URL the *browser* can reach (the host's published port), not an
  internal Docker DNS name. Verified by actually building the image and
  running the container — confirmed serving real content on port 5173
  with the correct API URL baked into the built JS bundle, not just
  that `docker compose config` parses.

Everything described in the master specification (Phases 0-10, Sections
36-40, 45, 46, and 48) is now implemented.

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

Pass an optional `match_score` (the discovery graph's
`MatchResult.overall_score` for this job) to enable `hybrid` approval
mode's auto-approve carve-out (Section 48):

```bash
curl -X POST http://localhost:8000/api/applications \
  -H "Content-Type: application/json" \
  -d '{
    "job": {...},
    "form_page_url": "...",
    "match_score": 95.0
  }'
```

With `config/automation.yaml`'s `approval.mode: hybrid`, a high enough
score plus high enough field-mapping confidence (both configurable,
`hybrid_min_score`/`hybrid_min_confidence`) and no field left needing a
human skips `MANUAL_APPROVAL_REQUIRED` entirely — the response comes
back `"status": "completed"` immediately. Omitting `match_score`, or
`approval.mode: manual` (the default), always pauses for approval.

### Trying the Greenhouse adapter

`app/portals/greenhouse/` is the first real (non-mock) portal integration —
discovery and job-detail loading go through Greenhouse's actual public
Job Board API (`https://boards-api.greenhouse.io/v1/boards/<token>/jobs`,
no auth required, no scraping):

```python
import asyncio
from app.portals.greenhouse.adapter import GreenhouseAdapter

async def main():
    adapter = GreenhouseAdapter("gitlab")  # any company on Greenhouse
    jobs = await adapter.discover_jobs({})
    print(f"{len(jobs)} real jobs")

    details = await adapter.get_job_details(jobs[0])   # full description
    job = await adapter.normalize_job(details)          # -> NormalizedJob
    print(job.title, job.company, job.url)

asyncio.run(main())
```

To enable it in the discovery graph itself, add a board token to
`config/portals.yaml` (it ships empty, so a fresh install is unaffected):

```yaml
portals:
  greenhouse:
    boards: ["gitlab"]   # or any company's Greenhouse board token
```

With that set, `POST /api/runs` discovers from the real board instead of
the local mock portals — same graph, same scoring, same guardrails, same
`/api/runs/{id}/resume` interrupt flow, zero code changes.

Verified live against GitLab's actual careers board: 201 real jobs
discovered, a full 7,579-character job description fetched via the real
detail endpoint, and — the important part — **read-only** field detection
(`detect_fields`, no fill, no submit) against the real live application
page, correctly finding 22 real fields including a genuinely nuanced
screening question ("Are you subject to any employment agreements and/or
post-employment restrictions...?") that the mapper correctly left for a
human (0.00 confidence) rather than guessing.

One real limitation this surfaced: Greenhouse splits the name into
`first_name`/`last_name` fields, but Phase 5's mapper only has one "name"
pattern (matched against `resume.name`, which Phase 1 never splits either)
— both fields get the same mapping today. Fixing this properly means
teaching Phase 1's parser to extract a structured name, which is out of
this phase's scope; noted here rather than silently left for someone to
rediscover.

`prepare_application`/`fill_application`/`validate_application` are fully
implemented (they delegate straight to `app/browser/forms.py`, the same
Phase 5/6 code already exercised against local fixtures) but are
deliberately **not** demonstrated against a live company's application
form in this README or in the automated test suite — Section 42 keeps
local fixtures as the primary/repeatable test environment, and filling a
real company's real form isn't necessary to prove the adapter works.
`submit_application()` always returns `{"status": "dry_run_ready",
"submitted": False}` while `AUTOMATION_DRY_RUN=true` (the enforced
default) and raises `NotImplementedError` otherwise — there is no code
path in this repository that actually submits anywhere yet.

### Trying the Lever adapter

`app/portals/lever/` is the second real (non-mock) portal integration —
discovery and detail-fetching go through Lever's actual public Postings
API (`https://api.lever.co/v0/postings/<company>?mode=json`, no auth
required, no scraping):

```python
import asyncio
from app.portals.lever.adapter import LeverAdapter

async def main():
    adapter = LeverAdapter("leverdemo")  # Lever's own public demo board
    jobs = await adapter.discover_jobs({})
    print(f"{len(jobs)} real postings")

    details = await adapter.get_job_details(jobs[0])
    job = await adapter.normalize_job(details)         # -> NormalizedJob
    print(job.title, job.company, job.url)

asyncio.run(main())
```

To enable it in the discovery graph, add a company to
`config/portals.yaml` (it ships empty, so a fresh install is unaffected):

```yaml
portals:
  lever:
    companies: ["leverdemo"] # or any company's Lever site id
```

With that set, `POST /api/runs` discovers from the real board instead of
the local mock portals — same graph, same scoring, same guardrails, same
`/api/runs/{id}/resume` interrupt flow. Greenhouse and Lever can both be
configured together; `app/portals/registry.py` fans out to every
registered adapter without any portal-specific code in the graph.

Verified live against Lever's own public demo board: 388 real postings
discovered, a real posting's plain-text description fetched via the real
detail endpoint, and — the important part — real field detection *and*
mapping against the real live application page: 50 real fields found
(name, email, phone, resume upload, plus a rich EEO/demographic set —
pronouns, gender, race/ethnicity, veteran status, disability status),
with exactly `name`/`email`/`phone` auto-mapped from the candidate
profile and all other 46 fields correctly left `requires_human=True` —
including every sensitive category, per Section 18 (see `SECURITY.md`'s
"Sensitive form questions").

**One real bug found and fixed here**: Lever splits a posting's
descriptive page (`hostedUrl` — zero form fields, confirmed live) from
its actual application form (`applyUrl`, `hostedUrl` + `/apply`) —
unlike Greenhouse, where the posting page *is* the application page.
Using `hostedUrl` as `job.url` (a reasonable-looking first guess, since
that's the field Lever's docs describe as "the" job URL) would have
made `prepare_application` navigate to a page with no form on it at
all — 0 fields detected, silently. `_to_common_raw_shape` now sets
`url` to `applyUrl` and keeps `hostedUrl` in `metadata["posting_url"]`
for anyone wanting the human-readable posting instead. Found by
actually running field detection against a live board rather than
trusting the API docs' field-naming — see the README's "Notes for
contributors" for the second bug this same live-verification pass
caught (an epoch-milliseconds datetime).

### Running the dashboard

Backend first (the API — see Quickstart above), then the frontend:

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev            # http://localhost:5173
```

The backend's CORS middleware (`app/main.py`) allows `localhost:5173`/
`127.0.0.1:5173` specifically — if you run the dev server on a different
port, add it there too.

- **Overview** — stat tiles (jobs discovered today, queued, rejected,
  applications today/week/month, human-review queue size), a "Start
  Discovery Run" button, recent runs, and a human-review preview.
- **Jobs** — filterable list (status/company/min score) + a detail page
  with the score breakdown (title/skills/experience/industry/location/
  compensation, each 0-100) as bars, matched/missing skill chips, and the
  full job description.
- **Applications** — every application with its status and, when paused,
  which interrupt it's waiting on.
- **Human Review** — the unified queue from `GET /api/human-actions`
  (both Phase 3 run-level and Phase 6 application-level interrupts), with
  a purpose-built resolve form per interrupt reason: queue/reject buttons
  per job for `HUMAN_REVIEW_REQUIRED`, a text input per field for
  `UNKNOWN_REQUIRED_FIELD`, an approve/reject button showing every field
  about to be submitted for `MANUAL_APPROVAL_REQUIRED`, and simple
  code/confirm inputs for `OTP_REQUIRED`/`CAPTCHA_REQUIRED`.
- **Analytics** — jobs by status/score bucket, applications by status/
  source, top matched/missing skills, companies applied to. Deliberately
  **does not** show response rate, interview rate, or time-to-response —
  this system has no inbound email/webhook monitoring, so there is no data
  source for real employer responses; showing those numbers would mean
  fabricating them, so the page says so instead of guessing.
- **Settings** — reads and writes `config/automation.yaml`, `scoring.yaml`,
  `search.yaml`, `portals.yaml`, `notifications.yaml` directly (as JSON in
  a text editor per section) via `GET`/`PUT /api/settings` — no restart
  needed, but a save rewrites the file wholesale (`yaml.safe_dump`), so
  hand-written comments in those files don't survive an edit made through
  this page. Editing the `automation` section's `scheduler` block
  immediately reloads the running scheduler (Phase 9).

### Trying the scheduler and notifications

The scheduler ships disabled (`config/automation.yaml`'s
`scheduler.enabled: false`) — a fresh install never runs anything on a
timer until you turn it on:

```yaml
scheduler:
  enabled: true
  timezone: UTC
  schedules:
    - type: cron
      expression: "0 9 * * 1-5" # weekdays at 9am
    - type: interval
      hours: 2
  daily_summary_hour: 18 # 0-23, local to `timezone`
```

Each entry drives a discovery run — the same `graph.service.start_run()`
that `POST /api/runs` calls, so a scheduled run behaves identically
(same scoring, same guardrails, same human-review pause) to a manual
one. A daily-summary job is registered automatically whenever
`enabled: true`, independent of `schedules`. Both take effect
immediately on save via `PUT /api/settings` — no restart, since the
scheduler's `reload()` re-reads the file and replaces every job.

Notifications (`config/notifications.yaml`) fire on run completed/
failed, application submitted/failed, human intervention required, and
the daily summary:

```yaml
notifications:
  providers:
    console: { enabled: true } # on by default, zero setup
    webhook: { enabled: false, url: "" }
    email:
      enabled: false
      smtp_host: ""
      smtp_port: 587
      smtp_username: ""
      smtp_password: "${NOTIFICATIONS_SMTP_PASSWORD}"
      from_address: ""
      to_address: ""
    desktop: { enabled: false } # notify-send; no-ops if unavailable
```

One channel failing (a bad webhook URL, an unreachable SMTP server)
never blocks another — `notify_all` catches and logs per-provider.

Verified live: a 25-second `interval` schedule firing two real
discovery runs back to back (console log lines and a real webhook POST
captured by a local HTTP receiver for both the `human_intervention_required`
and `run_completed` events), the daily-summary job invoked directly with
real data producing a correct summary, an application's
`application_submitted` notification after approval, and a live
`PUT /api/settings` disabling the scheduler mid-run — confirmed no
further runs fired afterward.

## Using the CLI

`jobagent` (Section 46) is installed automatically by `pip install -e .`
(it's a `[project.scripts]` entry point, `app/cli/main.py`) and works
without the API server running — it calls the same service functions
`app/api/routes/` calls, directly, in-process.

```bash
jobagent doctor                              # diagnose the local environment
jobagent profile import resume.pdf           # [--cover-letter cover.pdf]
jobagent profile show
jobagent run                                 # discover -> normalize -> dedupe -> score -> guard -> finalize
jobagent applications list                   # [--status dry_run_ready]
jobagent human pending                       # both run-level and application-level interrupts
jobagent human resolve <id> --decisions '{"<job_id>": "queue"}'
jobagent human resolve <id> --payload '{"approved": "true"}'
```

`doctor` never fails the command itself — it's diagnostic, reporting
`[OK]`/`[FAIL]` per check (Python version, database, Playwright browser,
Ollama reachability, configured LLM, whether a resume has been
imported, `.env` presence, required data directories) so you always get
a full picture rather than stopping at the first problem. `run`'s
`--dry-run`/`--no-dry-run` flag exists for interface parity with the
spec but is informational only — `AUTOMATION_DRY_RUN` (env var /
`config/automation.yaml`) is what actually governs this, globally, the
same way for the CLI, the API, and the scheduler.

Every command's stdout is clean, parseable output (JSON where the
underlying result is structured, plain text otherwise) — nothing else
writes there. All logging (including a fired notification's console
line) goes to stderr, so `jobagent run | jq .metrics` works exactly as
expected. This wasn't true on the first pass — see the README's "Notes
for contributors" entries on `app/core/logging.py` for the two bugs the
CLI's own tests caught before this held.

## Local LLM setup (Ollama)

The platform defaults to a local Ollama instance and never requires a paid
API key.

```bash
# install Ollama separately: https://ollama.com
ollama pull <your-chosen-model>
export OLLAMA_MODEL=<your-chosen-model>

# only needed for real embeddings (app/llm/embeddings.py) — optional
ollama pull nomic-embed-text
export OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

No specific model is hardcoded anywhere in the codebase — set `OLLAMA_MODEL`
to whatever you have pulled locally.

`app/llm/` (Sections 36-39) is real, working infrastructure — a provider
abstraction (`base.py`), an `OllamaProvider` (`ollama.py`, structured
JSON output via Pydantic schema validation), capability-based model
routing (`router.py`, Section 37 — every capability defaults to the same
configured model today), an embedding provider with in-process caching
(`embeddings.py`, Section 38), a versioned prompt loader
(`prompts.py`) reading `prompts/*.md` (Section 39), and startup health
checks (`health.py`, Section 36's four required checks: reachable, model
exists, returns valid JSON, structured output validates).

**Nothing in the scoring/matching/extraction hot path calls any of it
yet** — that's a deliberate scoping decision, not an oversight.
`app/matching/semantic.py`'s deterministic token-overlap fallback (used
by `title.py` for titles outside every known family) was built from the
start with an embedding-shaped swap-in point in mind, but its only
caller runs synchronously inside `score_job()`, and threading a real
async embedding call through that path is a genuine refactor of
already-tested Phase 2 code — left for when a concrete need justifies
it, not bundled into building the LLM plumbing itself. The seven
`prompts/*.md` templates (resume_parser, job_parser, job_matcher,
form_classifier, answer_generator, cover_letter, supervisor) are real,
usable prompt assets, each with an explicit note on whether/how it's
wired up.

**No real Ollama instance was available in this project's development
session** (`ollama` isn't installed here) — every `app/llm/` test mocks
the HTTP layer (`tests/unit/test_llm_*.py`). The one thing verified for
real, not mocked, is exactly the scenario a fresh install without Ollama
hits: `tests/integration/test_app_startup.py` runs the actual app
lifespan against this environment's real absence of Ollama and confirms
it starts cleanly rather than crashing (Section 36's "DO NOT crash
entire application" requirement) — everything else about a live Ollama
integration is unverified pending a real local model to test against.

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
  cli/               `jobagent` console script (Section 46) — profile/
                      run/applications/human/doctor, calling the same
                      services app/api/routes/ does, no server required
  core/            configuration, logging
  api/              FastAPI routes (health, profile, runs, applications,
                      jobs, human_actions, analytics, settings — Phase 8)
  database/         async SQLAlchemy session/models (candidate_profiles,
                      jobs, applications, automation_runs,
                      human_interventions)
  profile/           candidate profile parsing — loader/parser/services (Phase 1)
  jobs/              NormalizedJob + portal-agnostic normalize_job() (Phase 2)
  matching/          job-candidate scoring engine — title/skills/experience/
                      salary/location/industry, all rule-based (Phase 2)
  graph/             LangGraph supervisor (state/nodes/graph/service,
                      mocked portals until Phase 7 — Phase 3) + the apply
                      subgraph (apply_state/apply_nodes/apply_graph/
                      apply_service — Phase 6) + persistence.py, the
                      dashboard's write/read layer (Phase 8)
  agents/            LLM-driven graph-node steps (still empty — app/llm/
                      is the provider infrastructure; no graph node
                      calls into it yet, see "Local LLM setup" below)
  guardrails/        deterministic policy engine — models/policy/engine,
                      12 checks, wired into graph/nodes.py's policy_guard (Phase 4)
  browser/           Playwright automation — manager/sessions/selectors/
                      forms/mapping/detection/screenshots/errors (Phase 5-6)
  portals/           base/ (JobPortalAdapter interface), registry.py
                      (portal-id -> adapter dispatch, Phase 10), html.py
                      (shared strip_html), greenhouse/ + lever/ (each:
                      client.py real public API, adapter.py full interface,
                      application methods delegate to browser/) (Phase 7, 10)
  analytics/         summary/platforms/scores computation, shared by the
                      API routes and the scheduler's daily-summary job (Phase 9)
  scheduler/         SchedulerService wrapping APScheduler — cron/interval
                      schedules from config, independent from LangGraph (Phase 9)
  notifications/     NotificationProvider abstraction — console/webhook/
                      email/desktop implementations (Phase 9)
  llm/               local LLM provider abstraction — base/ollama/router/
                      embeddings/prompts/health/schemas/errors, wired
                      into app.main's startup health check only
  observability/ security/
config/              YAML domain configuration
prompts/             7 versioned LLM prompt templates (resume_parser,
                      job_parser, job_matcher, form_classifier,
                      answer_generator, cover_letter, supervisor) — real
                      content, none wired to a code path yet
tests/               unit / integration / e2e / fixtures / mocks
migrations/           Alembic migrations
frontend/            Vite + React + TypeScript + Recharts dashboard (Phase 8) —
                      api/ (client + types), pages/ (Overview, Jobs, JobDetail,
                      Applications, HumanReview, Analytics, Settings),
                      components/, hooks/
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
- **A package directory and a same-named module can't coexist.** Phase 0
  scaffolded `app/portals/base/` as an (empty) package. Writing
  `app/portals/base.py` for Phase 7's `JobPortalAdapter` silently shadowed
  it — Python resolved imports to the pre-existing empty package, not the
  new file, producing a confusing `ImportError` at app startup rather than
  at the write site. The interface now lives in `app/portals/base/__init__.py`
  instead. If `git status`/an editor shows both `x.py` and `x/` under the
  same parent, one of them is dead weight — find out which before adding
  code to either.
- **New adapters must not change `config/portals.yaml`'s shipped
  defaults.** `greenhouse.boards` defaults to `[]` specifically so
  `load_search_policy_node` keeps falling back to the local mock portals
  for every test and fresh install — the automated suite runs against the
  real config directory (`CONFIG_DIR=./config`), so a non-empty default
  here would make CI depend on live network access. Verified with a
  dedicated regression test
  (`test_default_config_still_falls_back_to_mock_portals`).
- **SQLite silently drops tzinfo on read, even for a
  `DateTime(timezone=True)` column.** `app/graph/persistence.py` writes
  `datetime.now(UTC)` everywhere, but reading a `JobRecord`/
  `ApplicationRecord` back out of SQLite gives a naive `datetime` —
  comparing it directly against a fresh `datetime.now(UTC)` (as
  `/api/analytics/summary` does for "today"/"this week"/"this month")
  raises `TypeError: can't compare offset-naive and offset-aware
  datetimes`. `app/api/routes/analytics.py::_as_utc` re-attaches `UTC` to
  a naive value before comparing — safe here specifically because every
  datetime this app writes already *is* UTC. Postgres wouldn't hit this
  (it preserves tzinfo), so it's easy to miss in code review; if you add
  another "since X" comparison against a DB-read timestamp, route it
  through `_as_utc` too.
- **Resolving one application-level interrupt can immediately surface a
  different one — resolving isn't the same as completing.** The apply
  subgraph's `interrupt()` calls are sequential within a run (Section 19:
  unknown field → challenge pages → manual approval), so
  `POST /api/human-actions/{id}/resolve` (or
  `POST /api/applications/{id}/resume` directly) can come back with
  `status: "waiting_human"` again, just for a *different* `reason` — e.g.
  answering an `UNKNOWN_REQUIRED_FIELD` for a job with no name/phone on
  file immediately re-pauses at `MANUAL_APPROVAL_REQUIRED`. Confirmed live
  against the actual dashboard: the Human Review page correctly re-renders
  with the new interrupt's resolve form rather than showing "done" after
  one submission — if you build another interrupt-resolving UI, don't
  assume one resolve call means the underlying run finished.
- **APScheduler's `Job.next_run_time` is an unset `__slots__` attribute,
  not `None`, before the scheduler has actually started.** `Job` declares
  it in `__slots__`; a job added via `add_job()` before `.start()` (or
  read back before the scheduler has computed a fire time) raises
  `AttributeError: 'Job' object has no attribute 'next_run_time'` on
  direct access — Python's `__slots__` semantics for a never-assigned
  slot, not a `None` default. `SchedulerService.list_jobs()` (`app/
  scheduler/service.py`) uses `getattr(job, "next_run_time", None)`
  rather than `job.next_run_time`; do the same for any other code that
  inspects a job before start.
- **A discovery run's `jobs` table rows can lag the graph's own state by
  one node.** `persist_run_result` (Phase 8) only sees whatever keys are
  already present in the interrupted state dict — a job the scorer
  routed to the `human_review` band isn't recorded with `status:
  "human_review"` in the `jobs` table until *after* the run is resumed
  and the node that builds `human_review_jobs` actually completes; while
  a run sits paused, its human-review-band jobs simply aren't in the
  table yet (queued/rejected/duplicate jobs from earlier nodes are).
  Noticed live in Phase 9's scheduler verification — `GET /api/jobs`
  right after a scheduled run paused showed only the duplicate, not the
  two pending-review jobs, until the run was resumed.
- **A portal's "job URL" and its "application form URL" are not
  guaranteed to be the same page — verify live, don't assume from field
  naming.** Greenhouse's `absolute_url` happens to be both; Lever splits
  them into `hostedUrl` (the descriptive posting — confirmed zero `<form>`
  elements) and `applyUrl` (`hostedUrl` + `/apply`, where the real fields
  live). `app/portals/lever/adapter.py::_to_common_raw_shape` sets
  `NormalizedJob.url` to `applyUrl` specifically because
  `prepare_application` navigates straight to `job.url` — using the more
  obviously-named `hostedUrl` would have produced a working-looking
  adapter that silently detected 0 fields on every real application
  attempt. Caught only because Phase 10's live verification ran real
  field detection against the real page rather than stopping at "the API
  call succeeded." If you add a fourth portal, check whether its listing
  page and apply page are actually the same URL before assuming so.
- **A raw API timestamp's units aren't always seconds.** Pydantic v2
  parses a bare `int`/`float` passed to a `datetime` field as Unix epoch
  *seconds* by default. Lever's `createdAt` is epoch *milliseconds* —
  passed straight through, `1553186035299` lands somewhere in the year
  51157, not 2019. `app/portals/lever/adapter.py::_epoch_ms_to_iso`
  divides by 1000 before handing it to `NormalizedJob`. Worth an explicit
  check any time a new portal's raw timestamp field isn't already an
  ISO8601 string (Greenhouse's `first_published` is; Lever's `createdAt`
  isn't).
- **Phase 7 hardcoded Greenhouse directly into the supervisor** (a
  `portal.startswith("greenhouse:")` branch in `app/graph/nodes.py`) —
  exactly what Phase 10 explicitly rules out repeating ("do not modify
  the supervisor for every new portal"). Adding Lever the same way would
  have meant a second, near-identical branch. Instead, Phase 10 pulled
  the dispatch logic into `app/portals/registry.py` (a plain
  `dict[str, PortalRegistration]`, deliberately a mutable dict rather
  than a frozen structure so tests can `monkeypatch.setitem` a fake
  adapter in) and rewrote `nodes.py` to call `build_adapter`/
  `resolve_enabled_real_portals` generically. A fourth portal needs a new
  `app/portals/<name>/` module plus one registry entry — `nodes.py`
  itself should never need to change again for this reason.
- **`configure_logging()` defaulted every log line to stdout, with no
  way to separate a command's actual output from its diagnostics.**
  Fine for the server (its stdout *is* its log stream, nothing else
  reads it) but broken for `jobagent`: a notification's console log line
  landing in the middle of what was supposed to be clean JSON output
  broke `jobagent run | jq`. Found by the CLI's own tests parsing
  `result.stdout` as JSON and getting `JSONDecodeError`. Fixed with a
  `stream: TextIO = sys.stdout` parameter (`app/core/logging.py`) — the
  server keeps its existing default; `app/cli/main.py`'s startup
  callback passes `stream=sys.stderr` instead.
- **`cache_logger_on_first_use=True` meant a second `configure_logging()`
  call in the same process could break an unrelated logger.** Structlog
  caches each *individual* module-level `logger = get_logger(__name__)`
  (the pattern used throughout this codebase) the first time it actually
  logs something — bound to whatever stream was configured *at that
  moment*. `app/cli/main.py`'s callback calls `configure_logging()` once
  per invocation (correct for a real CLI process, which only ever does
  this once before exiting) — but running many invocations in one
  process, exactly what `CliRunner` does across a test file, meant a
  later, wholly unrelated test's first-ever log call could land while a
  prior CLI invocation's now-closed stream was still the cached target,
  raising `ValueError: I/O operation on closed file` in a test file that
  never touched the CLI. A `structlog.reset_defaults()` teardown between
  CLI tests looked like a fix but wasn't sufficient — it resets the
  *global* config, not an already-populated per-logger cache. The actual
  fix is in `app/core/logging.py`: `cache_logger_on_first_use=False`. If
  you ever see this exact `ValueError` in a test that doesn't reference
  logging at all, this is almost certainly why — check for it before
  reaching for a per-test workaround, which won't hold.

## Development workflow

This project is built in explicit phases (see the architecture doc's
implementation plan). Each phase stops for review before the next begins.
Phases 0-10 are complete, and LLM integration (Sections 36-39, never
gated behind a specific numbered phase in the original spec) has been
built as working provider/router/embeddings/prompt infrastructure —
but every scoring, matching, extraction, and guardrail decision in this
codebase remains deterministic, non-LLM code, by deliberate choice, not
because the infrastructure to do otherwise doesn't exist. See "Local LLM
setup (Ollama)" for exactly what is and isn't wired up.

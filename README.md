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

Everything else described in the architecture doc (portal adapters, browser
automation, dashboard, scheduler) lands in later phases.

## Quickstart

```bash
git clone <repo-url>
cd job-automation

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium   # only needed once browser automation phases land

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
"understanding" is an LLM task per the design spec, and the LLM isn't wired
up until Phase 6. So today's extractor pulls what regex/section-scanning can
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

If any job's score lands in the `human_review` band (60–74), the run
**pauses** there — the response comes back with `status: "waiting_human"`
and the pending job(s) needing a decision:

```json
{
  "run_id": "6b9e4e2c-...",
  "status": "waiting_human",
  "interrupt": {
    "reason": "SCORE_REQUIRES_HUMAN_REVIEW",
    "jobs": [{"job_id": "f5eafa7a-...", "title": "Head of Engineering", "company": "Gamma Systems", "score": 66.0}]
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

## Local LLM setup (Ollama)

The platform defaults to a local Ollama instance and never requires a paid
API key. This is wired in starting Phase 6; for now `config/llm.yaml` and
`.env.example` document the expected configuration:

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
  api/              FastAPI routes (health, profile, runs)
  database/         async SQLAlchemy session/models
  profile/           candidate profile parsing — loader/parser/services (Phase 1)
  jobs/              NormalizedJob + portal-agnostic normalize_job() (Phase 2)
  matching/          job-candidate scoring engine — title/skills/experience/
                      salary/location/industry, all rule-based (Phase 2)
  graph/             LangGraph supervisor — state/nodes/graph/service,
                      mocked portals until Phase 7 (Phase 3)
  agents/            LLM-driven agent steps (Phase 6+; empty for now)
  guardrails/        deterministic policy engine (Phase 4)
  browser/           Playwright automation (Phase 5)
  portals/           portal adapters (Phase 7+)
  llm/               local LLM provider abstraction (Phase 6)
  observability/ notifications/ scheduler/ security/
config/              YAML domain configuration
prompts/             versioned LLM prompts (Phase 6+)
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

## Development workflow

This project is built in explicit phases (see the architecture doc's
implementation plan). Each phase stops for review before the next begins —
the repository will not contain portal automation, browser automation, or
LLM integration until those phases are explicitly implemented.

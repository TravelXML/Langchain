# Architecture

This document describes both the current (Phase 0-6) implementation and the
target architecture the project is being built toward, phase by phase. Where
a component is not yet implemented, it is marked **(planned)**.

## System context

```mermaid
flowchart LR
    Candidate[Candidate] -->|resume, cover letter, preferences| Config[config/*.yaml + .env]
    Config --> Backend[FastAPI backend]
    Backend --> DB[(SQLite / PostgreSQL)]
    Backend --> LLM[Ollama local LLM]
    Backend -->|planned Phase 5+| Browser[Playwright browser automation]
    Browser -->|planned| Portals[Job portals: Greenhouse, Lever, Workday, ...]
    Backend --> Dashboard[React dashboard - planned Phase 8]
    Candidate --> Dashboard
```

## Current implementation (Phase 0-6)

```mermaid
flowchart TB
    Client -->|HTTP| FastAPIApp[app.main:app]
    FastAPIApp --> CorrelationMW[Correlation-ID middleware]
    FastAPIApp --> HealthRoute["/health"]
    FastAPIApp --> ProfileRoutes["/api/profile (GET, POST /import, PUT)"]
    HealthRoute --> Settings[app.core.config.Settings]
    HealthRoute --> DBCheck[check_database_connection]
    ProfileRoutes --> ProfileService[app.profile.profile_service]
    ProfileService --> ResumeService[resume_service]
    ProfileService --> CoverLetterService[cover_letter_service]
    ResumeService --> Loader[loader: pypdf text extraction]
    ResumeService --> Parser[parser: deterministic regex/section heuristics]
    ProfileService --> DBCheck
    DBCheck --> Engine[async SQLAlchemy engine]
    Engine --> SQLite[(SQLite dev / PostgreSQL prod)]
    Settings --> YamlLoader[YamlConfigLoader]
    YamlLoader --> YamlFiles["config/*.yaml"]
    ProfileService --> YamlLoader
```

Configuration is layered:

- **`Settings`** (`app/core/config.py`) — environment-driven (`.env`),
  process-level: database URL, LLM connection, dry-run/approval defaults.
- **`YamlConfigLoader`** — domain configuration under `config/*.yaml`
  (candidate preferences, scoring weights, search policy, automation
  limits, portal registry), with `${ENV_VAR}` interpolation and per-file
  caching.

Logging is JSON-structured (`structlog`), with a per-request correlation ID
bound via contextvars and a redaction processor that strips sensitive keys
(passwords, tokens, cookies, OTPs, secrets) before anything is emitted.

### Candidate profile (Phase 1)

```mermaid
flowchart LR
    PDF[resume.pdf] --> Loader[loader.extract_text_from_pdf]
    Loader --> Parser[parser.parse_resume_text]
    ConfigSkills["config/candidate.yaml skills"] --> Parser
    Parser --> ResumeExtraction["ResumeExtraction\n(every field: value/source/confidence)"]
    ResumeExtraction --> ProfileRecord[(candidate_profiles table)]
    CoverLetterPdf[cover_letter.pdf] --> CLLoader[loader.extract_text_from_pdf]
    CLLoader --> ProfileRecord
```

Extraction is **deterministic, not LLM-based** — per Section 2 of the design
spec, resume "understanding" is an LLM capability, but no LLM is wired up
yet (the phase list runs 0-10 and never assigns LLM integration a number —
Sections 36-39 describe it but it isn't gated behind a specific phase). So
Phase 1's parser only populates fields a defensible
rule can produce (regex for email/phone/years-of-experience, section-header
scanning for education/certifications/languages/achievements, vocabulary
matching for skills). Fields that genuinely need semantic understanding
(previous titles, companies, industries) are left as
`{"value": null, "confidence": 0.0, "source": "unextracted"}` rather than
guessed — see Section 17 ("never invent information missing from the
resume"). A future LLM-backed extractor fills the same `ExtractedField`
schema with `source="llm"` without changing any downstream consumer.

The system is single-candidate/local-first: `candidate_profiles` has exactly
one row, addressed by the fixed id `"default"` (see
`app/database/models/candidate_profile.py`).

### Job model + matching engine (Phase 2)

```mermaid
flowchart TB
    RawJob["raw job dict\n(portal-agnostic shape)"] --> Normalize[jobs.parser.normalize_job]
    Normalize --> NormalizedJob["NormalizedJob\n(id derived from source+external_id/url)"]

    NormalizedJob --> Scorer[matching.scorer.score_job]
    Preferences[CandidatePreferences] --> Scorer
    CandidateSkills["candidate skills + experience_years\n(from ResumeExtraction)"] --> Scorer

    Scorer --> Title[title.match_title]
    Scorer --> Skills[skills.match_skills]
    Scorer --> Experience[experience.score_experience]
    Scorer --> Salary[salary.score_salary]
    Scorer --> Location[location.score_location]
    Scorer --> Industry[industry.score_industry]

    ScoringYaml["config/scoring.yaml\nweights + thresholds"] --> Scorer

    Title --> Breakdown[ScoreBreakdown]
    Skills --> Breakdown
    Experience --> Breakdown
    Salary --> Breakdown
    Location --> Breakdown
    Industry --> Breakdown

    Breakdown --> Explanation[explanation.build_explanation]
    Explanation --> MatchResult["MatchResult\n(overall_score, breakdown, reason, recommendation)"]
```

Every sub-scorer is pure rule-based logic — no LLM, no embeddings. Section
16 calls for a hybrid model (`exact rules + keyword normalization + skill
aliases + embedding similarity + optional LLM review`); Phase 2 implements
the first three (`skills.py`'s alias table resolves e.g. "Amazon Web
Services" → "AWS"; `title.py`'s family table resolves "Chief Technology
Officer" → the "CTO" family). Embedding similarity (Section 38) and LLM
semantic review are later additions layered on top — `semantic.py`
currently provides a deterministic token-overlap fallback (used by
`title.py` for titles outside every known family) with the same shape an
embedding-based implementation would have, so swapping it in later doesn't
change any caller.

Scoring never invents data to fill gaps — a job that doesn't disclose a
salary or experience range scores that dimension neutrally rather than
being guessed at or penalized (Section 17). Weights (title 25 / skills 30 /
experience 15 / industry 10 / location 10 / compensation 10) and
recommendation thresholds (`priority_apply` ≥90, `normal_apply` ≥80,
`apply_if_capacity` ≥75, `human_review` ≥60, else `reject`) both come from
`config/scoring.yaml`, never hardcoded in Python.

`NormalizedJob` (`app/jobs/models.py`) is the common schema every portal
adapter will normalize into (Phase 7+); portal-specific fields go under
`metadata` rather than contaminating the shared model (Section 8). No
`jobs`/`job_scores` database tables exist — Phase 3 persists run state via
the LangGraph checkpointer (below) rather than dedicated SQL tables; a
`jobs` table arrives if/when something other than a single in-flight run
needs to query historical jobs (e.g. the Phase 8 dashboard).

### LangGraph supervisor (Phase 3)

```mermaid
flowchart TB
    START --> LoadProfile[load_candidate_profile]
    LoadProfile --> LoadPolicy[load_search_policy]
    LoadPolicy -->|Send: one per enabled portal| DiscoverA[discover_portal: mock_greenhouse]
    LoadPolicy -->|Send| DiscoverB[discover_portal: mock_lever]
    DiscoverA --> Normalize[normalize_jobs]
    DiscoverB --> Normalize
    Normalize --> Dedupe[dedupe_jobs]
    Dedupe --> Score[score_jobs]
    Score --> Guard[policy_guard]
    Guard -->|human_review jobs exist| Interrupt["interrupt()\npersist + pause"]
    Interrupt -.->|Command resume, later call| Guard
    Guard --> Finalize[finalize]
    Finalize --> END
```

Implemented in `app/graph/`: `state.py` (`JobAutomationState`, a `TypedDict`
with `Annotated[list, operator.add]` reducers so parallel portal nodes
accumulate into `discovered_jobs` without clobbering each other — Section
24's fan-out, done via LangGraph's `Send` API rather than manual
asyncio.gather), `nodes.py`, `mock_portals.py` (two fixture portals
standing in for Phase 7's real adapters — one deliberately shares a job
with the other, company/title-family/location-identical, to exercise cross-
portal dedupe), `graph.py` (wiring + the SQLite checkpointer), and
`service.py` (`start_run`/`resume_run`/`get_run_state`, backing
`/api/runs`).

**The interrupt is real, not a stub**: `policy_guard` calls LangGraph's
`interrupt()` when any job scores in the `human_review` band (60–74).
Everything before that call re-runs identically on resume (it's pure/
deterministic), then the call returns the human's decision instead of
pausing again. Verified manually end-to-end including a genuine process
restart between pause and resume (kill the server, start a new one, `POST
/api/runs/{id}/resume` still works) — see the README's
"Running a discovery pipeline" section.

Deliberately deferred to later phases: resume selection, answer
preparation, the portal apply graph, submission, and verification (Phase
5-7); analytics (Phase 8). The diagram below shows where Phase 3 fits in
the full target picture.

### Guardrail engine (Phase 4)

```mermaid
flowchart TB
    ScoreJobs[score_jobs] --> PolicyGuard[policy_guard]
    PolicyGuard -->|per non-rejected job| Engine[guardrails.engine.run_guardrails]
    AutomationYaml["config/automation.yaml\napplications_per_day / per_company"] --> Engine
    Engine --> Checks["12 checks (policy.py)"]
    Checks --> Precedence{"BLOCK > HUMAN_INPUT_REQUIRED > ALLOW"}
    Precedence -->|BLOCK| Rejected[rejected_jobs]
    Precedence -->|HUMAN_INPUT_REQUIRED| HumanReview[human_review_jobs]
    Precedence -->|ALLOW| ScoreRouting["fall back to the scorer's\nown recommendation"]
    ScoreRouting --> Queue[application_queue]
    ScoreRouting --> HumanReview
```

`app/guardrails/`: `models.py` (`GuardrailDecision` — `ALLOW`/`BLOCK`/
`HUMAN_INPUT_REQUIRED`, never a bare bool, so "blocked" and "needs a human"
can't be conflated), `policy.py` (12 checks: `minimum_match_score`,
`maximum_daily_applications`, `maximum_company_applications`,
`excluded_companies`/`_roles`/`_locations`, `minimum_salary`,
`experience_mismatch`, `required_work_authorization`,
`duplicate_application`, `resume_validation`, `mandatory_fields`), and
`engine.py` (orchestrates all 12, aggregates to one decision — BLOCK beats
HUMAN_INPUT_REQUIRED beats ALLOW).

**Guardrails have final say over the scorer, per Section 23** ("supervisor
must not bypass or override guardrails") — `policy_guard` runs every
non-rejected job through the engine after score-based routing, and a
guardrail can only make the outcome *more* restrictive (queue →
human_review → reject), never less. Verified live: a job scoring 91
(`priority_apply`) from an excluded company ends up in `rejected_jobs`,
its `reason` carrying both the original score explanation and the
guardrail note (`app/graph/nodes.py::_with_guardrail_note`).

**The concrete "never fabricate candidate information" guardrail**
(Section 17) is `check_experience_mismatch`: if the resume parser never
determined a number for the candidate's years of experience — Phase 1's
`ExtractedField.source == "unextracted"` — and the job states a minimum,
the check returns `HUMAN_INPUT_REQUIRED` rather than assuming eligibility
either way. It's the same provenance mechanism Phase 1 built for exactly
this purpose, not a separate new one. `required_work_authorization`
(Section 18) follows the identical pattern: `CandidatePreferences.
work_authorization` defaults to `None`, and stays `None` until the
candidate explicitly states it — never inferred.

No `applications`/`audit_events` tables exist yet, so
`maximum_daily_applications`/`maximum_company_applications` and
`duplicate_application` currently evaluate against `0`/`0`/an empty set
(`GuardrailContext`'s defaults) — the checks are fully implemented and unit
tested with non-trivial inputs, they just have no real history to count
against until Phase 7+ records actual submissions.

### Playwright form engine (Phase 5)

```mermaid
flowchart TB
    Page[Playwright Page] --> Detect[forms.detect_fields\none page.evaluate DOM walk]
    Detect --> Fields["list[DetectedField]\n(label, type, options, required, selector)"]
    Fields --> Mapping[mapping.map_fields]
    Profile[CandidateProfile] --> Mapping
    Mapping --> Mappings["list[FieldMapping]\n(candidate_value, confidence, requires_human, reason)"]
    Mappings --> Fill[forms.fill_form]
    Fields --> Fill
    Fill --> Filled[fields actually filled]
    Fill --> SkippedForHuman[fields left for a human]
    Fill --> Validate[forms.validate_form\nHTML5 checkValidity]
    Detect -.on failure.-> Screenshots[screenshots.capture_failure_artifacts\nPNG + HTML + console logs]
```

`app/browser/`: `manager.py` (launches/closes Chromium, headless
configurable), `sessions.py` (one persistent `BrowserContext` per portal,
cookies/storage saved to `data/browser_sessions/<portal>.json` so logging
in once doesn't mean logging in again next run), `selectors.py`
(`build_selector` — the priority order from Section 11: data-testid >
aria-label > role > name > id > CSS > text, pure function, no browser
needed to unit test it), `forms.py` (detect/fill/validate/upload, all
Playwright-dependent), `mapping.py` (the rule-based field-intelligence
module, Playwright-independent — pure function over `DetectedField` +
`CandidateProfile`), `screenshots.py`, `errors.py`, `models.py`
(`DetectedField`, `FieldMapping`, `FormFillResult`).

**Deterministic, not LLM-based — same reasoning as every prior phase.**
No LLM is wired up yet; `mapping.py`'s keyword-pattern table handles
label→field recognition, exactly the kind of task Section 2 says shouldn't
wait for one. A future LLM-backed classifier can replace the matching
logic without changing `FieldMapping`'s shape or any caller — same
swap-without-breaking-callers pattern as `semantic.py` in Phase 2.

**Confidence and "requires human" are never conflated with the field
simply having no known pattern.** Section 20's exact output shape
(`field`, `candidate_value`, `confidence`, `requires_human`) is
`FieldMapping`. Below `FORM_MAPPING_CONFIDENCE_THRESHOLD` (default 0.7,
`config` via `.env`) a field is never auto-filled even if a value exists —
verified live: an 18-year-experience, no-name-on-file candidate profile
run against the simple fixture form correctly filled email/phone/experience
and left `full_name` for a human, with the reason spelled out
(`"recognized as 'name' but no value is on file"`).

**Section 18's sensitive categories have no representation in the
candidate model at all** — gender, ethnicity, disability, veteran status,
religion, security clearance, criminal history always resolve to
`requires_human=True` in `mapping.py`, not because confidence is low but
because there is structurally nothing to guess from.

**Fixtures, not production portals** (Section 42): `tests/fixtures/html/`
has all ten required scenarios — simple form, multi-step, dropdown,
resume upload, required fields, an unrecognized field, OTP screen, CAPTCHA
screen, success page, failure page. The OTP/CAPTCHA screens are detected
and paused on starting Phase 6 (see below); success/failure page handling
is Phase 7's submission-verification job. All 11 e2e tests in
`tests/e2e/test_form_engine.py` run
against a real headless Chromium instance via `file://` URLs, no server
required.

### Apply subgraph — human interrupt (Phase 6)

```mermaid
flowchart TB
    START --> Detect[detect_and_map_fields]
    Detect -->|any field requires_human| InterruptUnknown["interrupt()\nUNKNOWN_REQUIRED_FIELD"]
    InterruptUnknown -.->|Command resume: field answers| Detect
    Detect --> Fill[fill_and_validate]
    Fill --> Challenges[check_challenges]
    Challenges -->|OTP screen detected| InterruptOtp["interrupt()\nOTP_REQUIRED"]
    InterruptOtp -.->|Command resume: otp_code| Challenges
    Challenges -->|CAPTCHA screen detected| InterruptCaptcha["interrupt()\nCAPTCHA_REQUIRED"]
    InterruptCaptcha -.->|Command resume: solved| Challenges
    Challenges --> Approval[manual_approval]
    Approval -->|approval.mode: manual, the default| InterruptApproval["interrupt()\nMANUAL_APPROVAL_REQUIRED"]
    InterruptApproval -.->|Command resume: approved| Approval
    Approval --> Finalize[finalize_application]
    Finalize --> END
```

A **separate, standalone graph** from the Phase 3 supervisor above — not
spliced into `application_queue`'s processing. Section 4's full picture
shows one continuous pipeline from discovery through submission, but
wiring the two together needs a real `application_queue` → apply hand-off,
which is Phase 7's job (once there's a real portal to apply *to*). Keeping
Phase 6 standalone meant zero regressions to Phase 3/4's already-passing
tests while still proving the interrupt mechanics for real.

Implemented in `app/graph/`: `apply_state.py` (`ApplicationState`),
`apply_nodes.py` (5 nodes, linear, one job at a time — matching Section
24's conservative `application_concurrency: 1`), `apply_graph.py` (wiring
+ its own checkpointer, same allow-listed-msgpack pattern as the
supervisor graph), `apply_service.py` (backing `/api/applications`).

**No live browser `Page` is ever held across an `interrupt()`.** Every
node that touches the browser opens and closes it within that single call
— `interrupt()` can pause for an arbitrary amount of real time, possibly
across a process restart (Section 26), and a `Page` object cannot survive
either. Verified: `launch_browser()` is called fresh inside
`detect_and_map_fields_node`, `fill_and_validate_node`, and once per page
inside `check_challenges_node`'s loop — never held in `ApplicationState`
itself (which only stores plain data: `job`, `candidate_profile`,
`field_mappings`, page URLs).

**Sequential `interrupt()` calls within one node work as LangGraph's docs
imply but this repo hadn't exercised before Phase 6** — `check_challenges_node`
loops over `challenge_page_urls` and can call `interrupt()` once per
challenge page; each `Command(resume=...)` satisfies the next pending call
in order, with everything before it re-running deterministically (it's
pure) rather than re-pausing. Confirmed via a standalone probe before
committing to the design (see the multi-interrupt test scenarios in
`tests/e2e/test_apply_graph.py`).

**Manual approval always fires last and is the real Section 48 default**:
`manual_approval_node` reads `config/automation.yaml`'s `approval.mode`
(default `"manual"`) and interrupts showing every field about to be
submitted (`MANUAL_APPROVAL_REQUIRED`, carrying the full `field_mappings`
list) — "hybrid" mode's score-based auto-approval carve-out isn't
implemented yet (falls back to manual), since there's no real
`application_queue` driving this graph yet to have a score to check.
`"automatic"` mode skips the interrupt entirely.

**Dry-run is enforced at the very last step regardless of approval**:
`finalize_application_node` checks `AUTOMATION_DRY_RUN` (default `true`)
*after* approval, not before — an approved application still ends in
`dry_run_ready`, never `submitted_mock`, until dry-run is explicitly
turned off (Section 47). Verified live with a genuine process kill/restart
between an `OTP_REQUIRED` pause and its resume — same guarantee Phase 3
already proved for the unrelated score-review interrupt.

### Target LangGraph workflow (Phase 3 done through Guard; rest planned)

```mermaid
flowchart TB
    START --> LoadProfile[Load Candidate Profile]
    LoadProfile --> LoadPolicy[Load Search Policy]
    LoadPolicy --> Supervisor[Supervisor / Planner]
    Supervisor --> PortalA[Portal Subgraph A]
    Supervisor --> PortalB[Portal Subgraph B]
    Supervisor --> PortalC[Portal Subgraph C]
    PortalA --> Aggregate[Aggregate Jobs]
    PortalB --> Aggregate
    PortalC --> Aggregate
    Aggregate --> Dedupe
    Dedupe --> Normalize
    Normalize --> Score[Score Jobs]
    Score --> Guard[Policy Guard]
    Guard --> Queue[Application Queue]
    Queue -.->|planned, Phase 5+| ResumeSel[Resume Selection]
    ResumeSel -.-> Answers[Answer Preparation]
    Answers -.-> ApplyGraph[Portal Apply Graph]
    ApplyGraph -.-> Validator[Pre-Submit Validator]
    Validator -.-> Auto{Automatic Approval?}
    Auto -.->|yes| Submit
    Auto -.->|no| Human[Human Review]
    Human -.-> Submit
    Submit -.-> Verify[Verify Submission]
    Verify -.-> Persist[Persist Results]
    Persist -.-> Analytics
    Analytics -.-> END
```

Note: implemented dedupe runs *after* normalize (needs title-family
canonicalization — Section 14's own "normalized title" matching key),
whereas this narrative diagram (carried over from the original design spec)
shows it before. See `app/graph/nodes.py::dedupe_jobs_node` for the
reasoning.

## Target portal subgraph (planned, Phase 7+)

```mermaid
flowchart TB
    START --> CheckSession[check_session]
    CheckSession --> Discover[discover_job]
    Discover --> Load[load_job]
    Load --> NormalizeJob[normalize_job]
    NormalizeJob --> Open[open_application]
    Open --> DetectForm[detect_form]
    DetectForm --> MapFields[map_fields]
    MapFields --> FillFields[fill_fields]
    FillFields --> ValidateFields[validate_fields]
    ValidateFields --> CheckVerify[check_verification]
    CheckVerify --> PreSubmitGuard[pre_submit_guard]
    PreSubmitGuard --> Submit[submit]
    Submit --> VerifySubmission[verify_submission]
    VerifySubmission --> SaveResult[save_result]
    SaveResult --> END
```

A portal subgraph failure must never terminate the supervisor run — failures
are caught, logged, and the run continues with the remaining portals.

## Target application state machine (planned)

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED
    DISCOVERED --> NORMALIZED
    NORMALIZED --> DUPLICATE
    NORMALIZED --> SCORED
    SCORED --> REJECTED
    SCORED --> QUEUED
    QUEUED --> PREPARING
    PREPARING --> FORM_OPEN
    FORM_OPEN --> FORM_FILLED
    FORM_FILLED --> WAITING_HUMAN
    WAITING_HUMAN --> READY_TO_SUBMIT
    FORM_FILLED --> READY_TO_SUBMIT
    READY_TO_SUBMIT --> SUBMITTING
    SUBMITTING --> SUBMITTED
    SUBMITTED --> VERIFIED
    SUBMITTING --> FAILED
    VERIFIED --> WITHDRAWN
    DUPLICATE --> [*]
    REJECTED --> [*]
    FAILED --> [*]
    WITHDRAWN --> [*]
    VERIFIED --> [*]
```

## Human-in-the-loop flow

Five real interrupt reasons exist today, across two graphs: the Phase 3
supervisor pauses when a job scores in the `human_review` band
(`/api/runs/{id}/resume`); the Phase 6 apply subgraph pauses for
`UNKNOWN_REQUIRED_FIELD`, `OTP_REQUIRED`, `CAPTCHA_REQUIRED`, and
`MANUAL_APPROVAL_REQUIRED` (`/api/applications/{id}/resume`). A dedicated,
unified `/api/human-actions` review queue spanning both graphs is still
planned — today each graph's own resume endpoint is authoritative for its
own interrupts. The mechanism (persist → notify → resolve → resume) is
identical across all five; only the *reason* and which endpoint handles it
differ.

```mermaid
sequenceDiagram
    participant Graph as LangGraph run
    participant State as Checkpointer (SQLite)
    participant User as Candidate
    Graph->>Graph: policy_guard: job in human_review band<br/>or apply_nodes: unknown field / OTP / CAPTCHA / manual approval
    Graph->>State: interrupt() persists state + reason automatically
    Graph-->>User: response carries status: "waiting_human" + reason
    User->>State: resolve via POST /api/runs/{id}/resume<br/>or POST /api/applications/{id}/resume
    State-->>Graph: Command(resume=decision)
    Graph->>Graph: continue from the exact interrupt() call site
```

## Database relationships (planned, expanded per phase)

```mermaid
erDiagram
    CANDIDATE_PROFILES ||--o{ RESUME_VERSIONS : has
    CANDIDATE_PROFILES ||--o{ COVER_LETTER_VERSIONS : has
    JOBS ||--o{ JOB_SCORES : scored_by
    JOBS ||--o{ APPLICATIONS : applied_via
    APPLICATIONS ||--o{ APPLICATION_STEPS : consists_of
    APPLICATIONS ||--o{ APPLICATION_ANSWERS : contains
    APPLICATIONS }o--|| PORTAL_ACCOUNTS : uses
    AUTOMATION_RUNS ||--o{ AGENT_RUNS : contains
    AUTOMATION_RUNS ||--o{ JOBS : discovers
    APPLICATIONS ||--o{ HUMAN_INTERVENTIONS : may_trigger
    APPLICATIONS ||--o{ AUDIT_EVENTS : logs
```

Phase 0 shipped only the async engine/session foundation
(`app/database/base.py`, `app/database/session.py`) and Alembic wiring
(`migrations/`) — no tables. Phase 1 adds the first one, `candidate_profiles`
(migration `99cc354684f4`), a simplified single-row version of the planned
`CANDIDATE_PROFILES`/`RESUME_VERSIONS`/`COVER_LETTER_VERSIONS` split above —
resume and cover-letter data live as JSON/text columns on one row rather
than versioned child tables, since there's exactly one local candidate and
no version history yet. Remaining tables are introduced as migrations in
the phases that need them — Phase 2 turned out to need none (it's a pure
scoring library with no discovery pipeline to persist yet); `jobs`/
`job_scores`/application tables arrive with the LangGraph pipeline in
Phase 3+, per Section 27 of the design spec.

## Deployment architecture (planned)

```mermaid
flowchart LR
    subgraph LocalMachine [Candidate's machine]
        Backend[FastAPI backend]
        SQLite[(SQLite)]
        Ollama[Ollama]
        Frontend[React dashboard]
        Backend --> SQLite
        Backend --> Ollama
        Frontend --> Backend
    end
    subgraph OptionalProd [Optional production deployment]
        BackendP[FastAPI backend]
        Postgres[(PostgreSQL)]
        Redis[(Redis - optional)]
        BackendP --> Postgres
        BackendP -.-> Redis
    end
```

Docker Compose is not required for local development (`make dev` runs
everything directly); it exists for the optional production path.

## Design principles enforced by the codebase

- **LLM only where semantic interpretation is required.** Deterministic
  code owns salary checks, location filtering, duplicate detection,
  guardrails, retries, scheduling, and submission verification.
- **Config over code.** Candidate preferences, scoring weights, automation
  limits, and portal registration live in `config/*.yaml`, not Python.
- **Dry-run and manual approval by default.** See `SECURITY.md`.
- **No portal-specific fields leak into the common job model** — they live
  under `NormalizedJob.metadata` (introduced Phase 2).
- **The supervisor orchestrates; it doesn't do the work.** `app/graph/graph.py`
  only wires nodes/edges/fan-out — DB access, scoring, and policy decisions
  are plain functions in `nodes.py` that the supervisor calls, never inline
  logic in the graph definition itself (Section 23).
- **A run's state is never only in Python memory.** Every graph invocation
  opens a fresh checkpointer connection to disk rather than holding one open
  for the process lifetime — proven by killing and restarting the server
  mid-run and still resuming correctly (introduced Phase 3).
- **Guardrails can only tighten an outcome, never loosen one.** The scorer
  proposes (Phase 2); guardrails dispose (Phase 4) — a check can downgrade
  `priority_apply` to `reject`, but nothing downstream can upgrade a
  guardrail's `BLOCK` back to `ALLOW` (Section 23).
- **Unknown is a distinct outcome from allowed or blocked.**
  `GuardrailDecision` is a three-value enum, not a bool — code can't
  accidentally treat "needs a human" the same as "denied" or "approved"
  (Section 17/18's fabrication-prevention rules depend on this distinction).
- **No feature develops against a live external site as its test
  environment.** Job discovery uses mock portals (Phase 3); the form
  engine uses local HTML fixtures (Phase 5, Section 42). Both are
  real code exercised by real automation (a real headless browser, a
  real LangGraph run) — only the *target* is local and disposable.
- **The system never solves what it must instead pause for.** CAPTCHA
  and OTP resume payloads are always a human's own input (a confirmation,
  a code read off their device) — never a solve attempt, a bypass, or a
  system-obtained value (Section 12, enforced in `apply_nodes.py`'s
  `check_challenges_node`).
- **A live resource is never held across an `interrupt()`.** The apply
  subgraph's nodes open and close the browser within a single node call;
  nothing that can't survive a process restart is ever stored in graph
  state (Section 26, Phase 6).

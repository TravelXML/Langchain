# Security

This document describes the safety model for the platform. It is updated as
each phase adds new surface area (portal credentials in Phase 7, browser
session handling in Phase 5, etc.).

## Automation safety boundaries

The system will **never**:

- Solve or bypass CAPTCHAs, or use a CAPTCHA-solving service.
- Spoof browser fingerprints or use stealth automation to evade detection.
- Rotate proxies to evade portal restrictions.
- Bypass anti-bot or login-protection controls.
- Fabricate candidate information (degrees, certifications, employment
  history, salary, skills, experience, visa status, work authorization,
  security clearance, notice period, or demographic information).
- Submit an application outside of `dry_run: false` + an explicit approval
  decision under the configured `approval.mode`.

If a CAPTCHA or OTP/MFA challenge is encountered, the run pauses, persists
state, and waits for manual completion — it is never worked around
programmatically. Implemented in Phase 6 (`app/graph/apply_nodes.py`'s
`check_challenges_node`, detecting via `app/browser/detection.py`): the
resume payload for a CAPTCHA is a plain `{"solved": true}` human
confirmation, never a solve attempt by the system itself; an OTP resume
carries the code the human read off their own device (`{"otp_code":
"..."}`), never one the system obtained on its own.

## Defaults

A fresh install starts with:

- `automation.dry_run: true` (`config/automation.yaml`) — no submission
  ever happens until a human explicitly flips this.
- `approval.mode: manual` — every application requires human approval.

Both must be changed explicitly and are never auto-escalated by the system.

`approval.mode: hybrid`'s auto-approve carve-out (Section 48) requires
both an explicit config change *and* a caller-supplied `match_score` on
every application (`apply_service.start_application`'s optional
`match_score` parameter) — an application started without one always
falls through to manual review, the same as `mode: manual`, regardless
of how high `hybrid_min_score`/`hybrid_min_confidence` are set. There is
no way to get an auto-approval without both conditions being true.

## Secrets

- Secrets live in `.env` (see `.env.example`); `.env` is gitignored and must
  never be committed.
- Secret-shaped settings use Pydantic `SecretStr` (see
  `fallback_llm_api_key` in `app/core/config.py`) so they are never
  accidentally rendered in logs, `repr()`, or error messages.
- Portal credentials (Phase 7+) will prefer OS credential/keyring storage
  over plaintext files where the platform supports it.

## PII storage

- Uploaded resumes/cover letters are saved under `data/uploads/` (see
  `UPLOAD_DIR` in `.env.example`) and the local database file lives under
  `data/*.db` — both directories are gitignored and must never be committed.
- The candidate profile database row stores raw resume/cover-letter text
  directly (Section 27's `candidate_profiles` table); this is local-only
  data by design (SQLite in dev) and is never sent anywhere except a
  future configured local LLM or a portal application form the candidate
  explicitly submits.
- Browser session cookies/local storage (`BROWSER_SESSIONS_DIR`, per-portal
  under `data/browser_sessions/`) and failure screenshots/HTML snapshots
  (`BROWSER_ARTIFACTS_DIR`, `data/browser_artifacts/`) can both contain PII
  or live session tokens — both directories are gitignored. Screenshots are
  only ever taken of pages the candidate's own automation is already
  interacting with, never sent anywhere off the local machine.

## Logging

- All logs are structured JSON via `structlog` (`app/core/logging.py`).
- A redaction processor strips any log field whose key matches a sensitive
  pattern (`password`, `otp`, `token`, `authorization`, `cookie`,
  `session_token`, `api_key`, `secret`) before it is emitted, regardless of
  call site.
- The exception handler in `app/main.py` logs the exception type and
  message only — never request bodies or headers, which may contain
  credentials.
- Cookies, authorization headers, session tokens, and passwords must never
  appear in traces, screenshots-on-failure metadata, or audit events
  (Phase 5+ / Phase 29 of the design spec).

## Error handling (Section 40)

- `app/core/errors.py`'s `JobAutomationError` (the shared base every
  exception in the codebase now inherits from) captures only a fixed,
  whitelisted set of context fields — url, portal, job_id, run_id,
  screenshot_path, step, timestamp — never a credential-shaped one, by
  construction: there is no field for a password/token/cookie/API key to
  land in even accidentally.
- `.to_dict()` strips the query string from any captured `url` before
  returning it, since a query string is the most common place a secret
  ends up in a URL by accident (an API key passed as `?key=...`) — none
  of this codebase's own captured URLs need one to be useful for
  debugging.
- This context flows into the same places already covered above: graph
  state's `errors` list (surfaced via `/api/runs`, `/api/applications`,
  the dashboard, and `jobagent`) and structured log lines — both already
  subject to the redaction processor and exception-handling rules
  described under "Logging".

## LLM privacy

- The default LLM provider is a local Ollama instance
  (`OLLAMA_BASE_URL`, default `http://localhost:11434`) — no data leaves
  the machine by default and no API key is required for the basic install.
- An OpenAI-compatible fallback provider exists in configuration
  (`fallback_llm_enabled`) but is **disabled by default** and must be
  explicitly enabled with an API key supplied via `.env`.
- `app/main.py`'s startup health check (`app/llm/health.py`) sends only
  a fixed, content-free test prompt (`{"ok": true}`) to verify Ollama is
  reachable and returns valid structured output — no candidate data, no
  job data, nothing profile-derived is ever included in it.
- Nothing in this codebase currently sends candidate or job data to any
  LLM at all — no scoring, matching, guardrail, or extraction decision
  routes through `app/llm/` yet (see `ARCHITECTURE.md`'s "LLM
  integration" section for the scoping decision). The two prompt
  templates that would draft candidate-facing content if wired up
  (`prompts/answer_generator.md`, `prompts/cover_letter.md`) both
  explicitly instruct the model to use only facts already in the
  candidate's own profile and never invent achievements, employers,
  dates, or credentials — consistent with "the system will never
  fabricate candidate information" above — but this is a property of
  the prompt text for future use, not something exercised by any
  request this codebase makes today.

## Sensitive form questions

Questions touching gender, ethnicity, disability, veteran status, religion,
medical information, work authorization, visa sponsorship, security
clearance, criminal history, or compensation declarations always require an
explicit stored candidate answer or human input — never inferred, and (no
LLM exists yet to be tempted to) never guessed by any code path either.
Implemented in `app/browser/mapping.py`: these categories have no
corresponding field anywhere in the candidate model, so they always resolve
to `requires_human=True` (Phase 5/6), and `app/guardrails/policy.py`'s
`check_work_authorization` applies the same rule at the guardrail layer
(Phase 4).

## Third-party network access

- `app/portals/greenhouse/client.py` reads Greenhouse's public,
  unauthenticated Job Board API
  (`boards-api.greenhouse.io/v1/boards/<token>/jobs`) — the request
  carries only a company's public board token and, for job details, a
  public job id; no candidate data is ever sent. It's read-only: no form
  is filled, no application is submitted from that client.
  `config/portals.yaml`'s `greenhouse.boards` defaults to `[]`, so a
  fresh install makes this call only after a board token is explicitly
  added.
- `app/portals/lever/client.py` (Phase 10) reads Lever's equivalent
  public Postings API (`api.lever.co/v0/postings/<company>`) the same
  way — a company identifier only, no candidate data, read-only.
  `config/portals.yaml`'s `lever.companies` defaults to `[]`, same
  fresh-install behavior as Greenhouse.
- The Webhook and Email notification providers (Phase 9,
  `config/notifications.yaml`) each make an outbound call — a JSON POST
  to `webhook.url`, an SMTP connection to `email.smtp_host` — but both
  default to `enabled: false`, so a fresh install makes neither call
  until explicitly configured. A `human_intervention_required` event for
  an application carries the same field values the dashboard's Human
  Review page shows for `MANUAL_APPROVAL_REQUIRED` — which can include
  the candidate's own name, email, and phone already on file, since the
  whole point of that notification is showing a human what's about to be
  submitted. This is not a leak (both a webhook and email address are
  destinations the operator explicitly configures themselves), but treat
  a configured webhook/email destination with the same care as the
  dashboard: it's shown the same data. Never resume *text* or any
  credential/session token — see "Logging" for what's redacted before
  anything is emitted.

## Dashboard (Phase 8)

- CORS (`app/main.py`) is scoped to exactly `http://localhost:5173` and
  `http://127.0.0.1:5173` — the Vite dev server's default origin, not a
  wildcard. Add another origin explicitly if you run the frontend
  elsewhere; don't switch this to `allow_origins=["*"]`.
- `PUT /api/settings` rewrites `config/*.yaml` directly and takes effect
  immediately (no restart) — this includes `automation.dry_run` and
  `approval.mode`, the two safety defaults above. There is no additional
  confirmation step at the API layer; the dashboard is a local,
  single-operator tool and this endpoint is exactly as trusted as editing
  the YAML file by hand.
- `frontend/`'s dev dependency `esbuild` (bundled via `vite@5.4.x`) has a
  known moderate advisory (GHSA-67mh-4wv8-2f99: the esbuild dev server
  will respond to cross-origin requests). It only affects `npm run dev`,
  never the production build, and the fix requires Vite 8 (Node ≥20 —
  this project currently targets Node 18). Not patched for that reason;
  revisit when the dev environment's Node version moves up.

## Scheduler + notifications (Phase 9)

- The scheduler ships disabled (`config/automation.yaml`'s
  `scheduler.enabled: false`) — a fresh install never runs anything on a
  timer. "Manual execution" (`POST /api/runs`) is unaffected either way.
- **No timing randomization was added anywhere in scheduling** — Section
  34 explicitly rules out building jitter intended to evade portal
  detection, and this codebase doesn't. A cron or interval schedule
  fires exactly when configured, nothing more.
- A scheduled run is `graph.service.start_run()` — the exact same
  function `POST /api/runs` calls — so it carries every safety property
  a manual run has: `automation.dry_run: true` enforced at the same
  final step, the same guardrail engine, the same human-review pause.
  Enabling the scheduler does not bypass approval; it only decides when
  a run *starts*, never whether it can submit anything unapproved.
- `EmailNotificationProvider` reads `smtp_password` from
  `config/notifications.yaml` via `${NOTIFICATIONS_SMTP_PASSWORD}`
  env-var interpolation (`YamlConfigLoader`'s existing mechanism) rather
  than a plaintext default in the file — set it in `.env`, never commit
  it in the YAML.
- `DesktopNotificationProvider` shells out to `notify-send` with the
  event's title/message as literal subprocess arguments
  (`asyncio.create_subprocess_exec`, not a shell string) — no shell
  injection surface regardless of notification content.

## Reporting

If you discover a security issue in this repository, open an issue
describing the concern without including exploit details for any live
third-party portal.

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

## LLM privacy

- The default LLM provider is a local Ollama instance
  (`OLLAMA_BASE_URL`, default `http://localhost:11434`) — no data leaves
  the machine by default and no API key is required for the basic install.
- An OpenAI-compatible fallback provider exists in configuration
  (`fallback_llm_enabled`) but is **disabled by default** and must be
  explicitly enabled with an API key supplied via `.env`.

## Sensitive form questions (planned, Phase 4/6)

Questions touching gender, ethnicity, disability, veteran status, religion,
medical information, work authorization, visa sponsorship, security
clearance, criminal history, or compensation declarations always require an
explicit stored candidate answer or human input — the LLM is never allowed
to infer or guess these.

## Reporting

If you discover a security issue in this repository, open an issue
describing the concern without including exploit details for any live
third-party portal.

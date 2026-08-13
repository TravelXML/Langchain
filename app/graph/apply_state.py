"""State for the per-application "apply" subgraph (Section 10/19, Phase 6).

Deliberately separate from ``JobAutomationState`` (the discovery/scoring
graph): this operates on exactly one job at a time — matching the
conservative ``application_concurrency: 1`` default (Section 24) — and its
shape (a single form to fill, a sequence of challenge screens to pass)
doesn't map onto the discovery graph's list-of-many-jobs state. Phase 7
wires the discovery queue into this graph rather than merging the two.

No live Playwright ``Page`` is ever stored here: every node that needs the
browser opens and closes it within that single node call. An
``interrupt()`` can pause for an arbitrary amount of real time — possibly
across a process restart (Section 26) — and a browser page cannot survive
either.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.browser.models import FieldMapping
from app.jobs.models import NormalizedJob
from app.profile.models import CandidateProfile


class ApplicationState(TypedDict, total=False):
    application_id: str

    job: NormalizedJob
    candidate_profile: CandidateProfile

    # Full URLs (file:// for local fixtures today, a real portal's https://
    # URLs once Phase 7 lands) — this graph has no opinion on where pages
    # come from, only that it's given one to open.
    form_page_url: str
    challenge_page_urls: list[str]

    field_mappings: list[FieldMapping]

    otp_code: str | None
    captcha_resolved: bool
    approved: bool | None

    status: str

    human_action_required: bool
    human_action_reason: str | None

    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]

"""Apply-subgraph nodes (Section 19: unknown field / OTP / CAPTCHA / manual
approval interruptions, all via LangGraph's real ``interrupt()``, not a
stub).

Every node that touches the browser opens and closes it within that single
call — no ``Page`` object is ever held across an ``interrupt()``, since the
pause can span an arbitrary amount of real time, possibly a process
restart (Section 26), and a browser page cannot survive either.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.browser.detection import is_captcha_screen, is_otp_screen
from app.browser.forms import detect_fields, fill_form, validate_form
from app.browser.manager import launch_browser
from app.browser.mapping import map_fields
from app.browser.models import FieldMapping
from app.core.config import get_settings, get_yaml_config_loader
from app.core.logging import get_logger
from app.graph.apply_state import ApplicationState

logger = get_logger(__name__)


async def detect_and_map_fields_node(state: ApplicationState) -> dict[str, Any]:
    async with launch_browser() as browser:
        page = await browser.new_page()
        await page.goto(state["form_page_url"])
        fields = await detect_fields(page)

    mappings = map_fields(fields, state["candidate_profile"])
    unknown = [m for m in mappings if m.requires_human]

    if unknown:
        answers: dict[str, str] = (
            interrupt(
                {
                    "reason": "UNKNOWN_REQUIRED_FIELD",
                    "fields": [{"field": m.field, "reason": m.reason} for m in unknown],
                }
            )
            or {}
        )
        mappings = [
            (
                m.model_copy(
                    update={
                        "candidate_value": answers[m.field],
                        "requires_human": False,
                        "source": "human",
                        "reason": "answered via unknown-field interrupt",
                    }
                )
                if m.requires_human and m.field in answers
                else m
            )
            for m in mappings
        ]

    still_unknown = [m.field for m in mappings if m.requires_human]
    return {
        "field_mappings": mappings,
        "human_action_required": bool(still_unknown),
        "human_action_reason": "UNKNOWN_REQUIRED_FIELD" if still_unknown else None,
    }


async def fill_and_validate_node(state: ApplicationState) -> dict[str, Any]:
    mappings: list[FieldMapping] = state.get("field_mappings", [])
    warnings: list[str] = []

    async with launch_browser() as browser:
        page = await browser.new_page()
        await page.goto(state["form_page_url"])
        fields = await detect_fields(page)

        fill_result = await fill_form(page, fields, mappings)
        if fill_result.errors:
            warnings.extend(fill_result.errors)

        invalid = await validate_form(page)
        if invalid:
            warnings.append(f"still invalid after fill: {', '.join(invalid)}")

    return {"warnings": warnings} if warnings else {}


async def check_challenges_node(state: ApplicationState) -> dict[str, Any]:
    otp_code: str | None = None
    captcha_resolved = False

    for page_url in state.get("challenge_page_urls", []):
        async with launch_browser() as browser:
            page = await browser.new_page()
            await page.goto(page_url)
            otp_present = await is_otp_screen(page)
            captcha_present = await is_captcha_screen(page)

        if otp_present:
            response: dict[str, str] = interrupt({"reason": "OTP_REQUIRED", "page": page_url}) or {}
            otp_code = response.get("otp_code")
        elif captcha_present:
            response = interrupt({"reason": "CAPTCHA_REQUIRED", "page": page_url}) or {}
            captcha_resolved = str(response.get("solved", "")).lower() in ("true", "yes", "1")
        else:
            logger.warning("challenge_page_not_recognized", page=page_url)

    return {"otp_code": otp_code, "captcha_resolved": captcha_resolved}


async def manual_approval_node(state: ApplicationState) -> dict[str, Any]:
    automation = get_yaml_config_loader().load("automation")
    mode = automation.get("approval", {}).get("mode", "manual")

    if mode == "automatic":
        return {"approved": True}

    # "manual" and "hybrid" both request a human decision here — Phase 6
    # doesn't yet implement hybrid's score/confidence auto-approval carve
    # -out (Section 48); that's a Phase 7+ refinement once there's a real
    # application queue driving this graph.
    decision: dict[str, Any] = (
        interrupt(
            {
                "reason": "MANUAL_APPROVAL_REQUIRED",
                "job_id": state["job"].id,
                "title": state["job"].title,
                "company": state["job"].company,
                "field_mappings": [m.model_dump() for m in state.get("field_mappings", [])],
            }
        )
        or {}
    )
    approved = str(decision.get("approved", "")).lower() in ("true", "yes", "1")
    return {"approved": approved}


async def finalize_application_node(state: ApplicationState) -> dict[str, Any]:
    if state.get("approved") is not True:
        return {"status": "rejected_by_human"}

    if get_settings().automation_dry_run:
        # Section 47: dry-run must never submit, regardless of approval.
        return {"status": "dry_run_ready"}

    # No real portal exists yet (Phase 7) — nothing to actually submit to.
    return {"status": "submitted_mock"}

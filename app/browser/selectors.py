"""Selector priority order (Section 11): data-testid > aria-label > role >
name > id > stable CSS > text > fallback. Avoids fragile deeply-nested CSS
paths — every selector here is a single attribute match.

Pure functions, deliberately Playwright-independent, so the priority logic
is unit-testable without a browser.
"""

from __future__ import annotations

from app.browser.errors import SelectorNotFoundError


def build_selector(
    *,
    testid: str | None = None,
    aria_label: str | None = None,
    role: str | None = None,
    name: str | None = None,
    elem_id: str | None = None,
    css: str | None = None,
    text: str | None = None,
) -> str:
    if testid:
        return f'[data-testid="{testid}"]'
    if aria_label:
        return f'[aria-label="{aria_label}"]'
    if role:
        return f'[role="{role}"]'
    if name:
        return f'[name="{name}"]'
    if elem_id:
        return f"#{elem_id}"
    if css:
        return css
    if text:
        return f'text="{text}"'
    raise SelectorNotFoundError("No selector strategy available for this element")

"""Shared HTML-to-plain-text helper for portal clients whose public APIs
return HTML-formatted job descriptions (Greenhouse's ``content``, Lever's
``description``/``lists[].content``) — not portal-specific, so it lives
here rather than duplicated per adapter.
"""

from __future__ import annotations

import html
import re


def strip_html(raw: str) -> str:
    """Unescape HTML entities once, then strip tags for a plain-text
    description."""
    unescaped = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", text).strip()

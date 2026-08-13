"""Deterministic text-similarity placeholder.

Section 38 calls for embedding-based similarity (skills, job titles,
descriptions, duplicate detection). Embeddings aren't wired up until that
phase, so this module provides a token-overlap fallback other matchers can
use today; swapping it for real embeddings later shouldn't require changing
any caller's signature — only this implementation.
"""

from __future__ import annotations

import re

_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def token_overlap_ratio(a: str, b: str) -> float:
    """Jaccard similarity over word sets, in [0.0, 1.0]."""
    tokens_a, tokens_b = _tokenize(a), _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)

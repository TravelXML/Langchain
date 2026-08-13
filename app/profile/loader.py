"""PDF text extraction.

Deliberately dumb: reads raw text from a PDF and nothing else. All semantic
interpretation happens in ``parser.py`` / the future LLM extractor — this
module has exactly one job so it stays easy to swap the PDF backend later.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


class PdfExtractionError(Exception):
    pass


def extract_text_from_pdf(path: Path) -> str:
    if not path.exists():
        raise PdfExtractionError(f"File not found: {path}")

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises various exception types for malformed PDFs
        raise PdfExtractionError(f"Failed to extract text from {path}: {exc}") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise PdfExtractionError(f"No extractable text found in {path}")
    return text

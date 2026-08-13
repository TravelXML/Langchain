"""Generates minimal, real PDF bytes for tests (dev-only reportlab dependency).

Kept out of ``tests/mocks`` because this produces genuine PDF bytes fed
through the real ``pypdf`` extraction path — it is a test fixture, not a
mock of one.
"""

from __future__ import annotations

import io

from reportlab.pdfgen import canvas


def build_pdf_bytes(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 750
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 16
    pdf.save()
    return buffer.getvalue()

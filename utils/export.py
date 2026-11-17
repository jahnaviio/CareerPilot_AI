"""Plain-text -> DOCX / PDF bytes for tailored resumes and cover letters."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape


def docx_bytes(text: str) -> bytes:
    from docx import Document
    d = Document()
    for line in text.splitlines():
        if line.strip():
            d.add_paragraph(line.strip())
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def pdf_bytes(text: str) -> bytes:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, topMargin=0.6 * inch, bottomMargin=0.6 * inch, leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    st = getSampleStyleSheet()["BodyText"]
    st.fontSize, st.leading = 10, 13
    story = []
    for line in text.splitlines():
        if line.strip():
            story += [Paragraph(escape(line.strip()), st), Spacer(1, 3)]
    doc.build(story or [Paragraph(" ", st)])
    return buf.getvalue()

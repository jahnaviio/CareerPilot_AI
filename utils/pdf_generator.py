"""Generate a downloadable PDF from tailored resume / cover letter text."""
from __future__ import annotations

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def create_resume_pdf(content: str, output_path: str) -> str:
    """Render plain text content into a simple, ATS-friendly PDF."""
    doc = SimpleDocTemplate(
        output_path,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    body_style.fontSize = 10
    body_style.leading = 13

    story = []
    for line in content.split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(line, body_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    return output_path

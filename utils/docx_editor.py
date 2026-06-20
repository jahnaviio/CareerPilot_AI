"""Generate a downloadable DOCX from tailored resume / cover letter text."""
from __future__ import annotations

from docx import Document


def create_docx(content: str, output_path: str) -> str:
    """Render plain text content into a simple DOCX document."""
    doc = Document()
    for line in content.split("\n"):
        line = line.strip()
        if line:
            doc.add_paragraph(line)
    doc.save(output_path)
    return output_path

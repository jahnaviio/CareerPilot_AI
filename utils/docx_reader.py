"""DOCX text extraction."""
from __future__ import annotations

from docx import Document


def read_docx(file_path: str) -> str:
    """Extract all paragraph text from a DOCX file."""
    document = Document(file_path)
    return "\n".join(p.text for p in document.paragraphs)

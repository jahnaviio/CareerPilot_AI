"""PDF text extraction."""
from __future__ import annotations

from pypdf import PdfReader


def read_pdf(file_path: str) -> str:
    """Extract all text from a PDF file."""
    reader = PdfReader(file_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)

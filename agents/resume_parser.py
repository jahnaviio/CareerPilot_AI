"""
Resume Parser agent.

Extracts raw text from an uploaded resume file (PDF or DOCX) and derives
a structured skill list from it. This is the entry point for the
"Resume Parser" feature — output feeds the resumes table and, from
there, every matching computation in the app.
"""
from __future__ import annotations

from dataclasses import dataclass

from agents.skill_matcher import extract_skills
from utils.docx_reader import read_docx
from utils.pdf_reader import read_pdf


@dataclass
class ParsedResume:
    raw_text: str
    skills: list[str]
    word_count: int


class UnsupportedFileTypeError(ValueError):
    pass


def parse_resume(file_path: str, filename: str) -> ParsedResume:
    """Parse a resume file from disk into text + extracted skills."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = read_pdf(file_path)
    elif lower.endswith(".docx"):
        text = read_docx(file_path)
    elif lower.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type for '{filename}'. Please upload a PDF, DOCX, or TXT file."
        )

    text = text.strip()
    skills = extract_skills(text)

    return ParsedResume(raw_text=text, skills=skills, word_count=len(text.split()))

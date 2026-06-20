"""Replace the PROFILE/SUMMARY section of an existing DOCX resume in place."""
from __future__ import annotations

from docx import Document

# Recognized section heading keywords. A paragraph only counts as a heading
# (not body text) if it's short and one of these keywords makes up most of
# it -- see _looks_like_heading. This avoids a bug where a body line that
# merely *mentions* "profile" (e.g. "Old profile text here.") gets
# misidentified as the PROFILE section header itself.
BOUNDARY_KEYWORDS = ("EDUCATION", "SKILLS", "EXPERIENCE", "PROJECTS")


def _looks_like_heading(text: str, keywords: tuple) -> bool:
    """
    A paragraph is treated as a section heading only if it's short (resume
    headings are a word or two, not full sentences) and one of the keywords
    makes up the bulk of it. This distinguishes a heading like "PROFILE"
    from a body sentence like "Old profile text here." which merely
    contains the word.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > 30:
        return False
    upper = stripped.upper()
    return any(keyword in upper for keyword in keywords)


def replace_profile_section(input_path: str, new_profile: str, output_path: str) -> str:
    """
    Find the PROFILE/SUMMARY heading paragraph, replace the paragraph(s)
    immediately after it with `new_profile`, stopping at the next
    recognized section heading.
    """
    doc = Document(input_path)
    profile_found = False
    replaced = False

    for para in doc.paragraphs:
        text = para.text.strip()

        if not profile_found and not replaced and _looks_like_heading(text, ("PROFILE", "SUMMARY")):
            profile_found = True
            continue

        if profile_found:
            if _looks_like_heading(text, BOUNDARY_KEYWORDS):
                break
            para.text = new_profile
            profile_found = False
            replaced = True

    doc.save(output_path)
    return output_path

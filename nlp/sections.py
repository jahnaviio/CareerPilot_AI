"""Rule-based resume section detection and text normalisation."""
from __future__ import annotations

import re

SECTION_ALIASES = {
    "summary": ["summary", "profile", "objective", "about me", "career objective", "professional summary"],
    "education": ["education", "academic background", "academics", "qualifications"],
    "skills": ["skills", "technical skills", "core competencies", "technologies", "tech stack", "skills & tools"],
    "projects": ["projects", "academic projects", "personal projects", "key projects", "project work"],
    "experience": ["experience", "work experience", "internships", "internship experience", "professional experience", "employment", "work history"],
    "certifications": ["certifications", "certificates", "licenses", "courses", "training"],
    "achievements": ["achievements", "awards", "honors", "accomplishments", "extracurricular", "activities", "leadership"],
    "links": ["links", "profiles", "contact", "social"],
}
_LOOKUP = {a: k for k, v in SECTION_ALIASES.items() for a in v}
BULLET = re.compile(r"^\s*[•\-\*–·▪●◦➢]\s*")


def _heading_key(line: str) -> str | None:
    s = re.sub(r"[^a-z& ]", "", line.strip().lower()).strip()
    if not s or len(line.strip()) > 40:
        return None
    return _LOOKUP.get(s) or _LOOKUP.get(s.replace(" and ", " & "))


def split_sections(text: str) -> dict[str, list[str]]:
    """Returns {section: [lines]}; unmatched leading lines go to 'header'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        key = _heading_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections[current].append(BULLET.sub("", line).strip() if BULLET.match(line) else line.strip())
    return {k: v for k, v in sections.items() if v}

"""
Shared skill vocabulary and rule-based matching logic.

The original codebase had three separate, slightly different hardcoded
skill lists (job_matcher.py, plus implicit ones in resume parsing).
This module is the single source of truth, and the scoring here is also
the deterministic fallback used whenever no LLM provider is configured —
so match scores always work, AI or not.
"""
from __future__ import annotations

import re

# Curated for AI/ML/Data/SWE internships — the population CareerPilot
# targets. Extend this list as the product covers more tracks.
SKILL_VOCABULARY: list[str] = [
    "Python", "Java", "C++", "JavaScript", "TypeScript", "SQL", "R",
    "Machine Learning", "Deep Learning", "Computer Vision", "NLP",
    "Generative AI", "Prompt Engineering", "RAG", "LLM",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "OpenCV",
    "Pandas", "NumPy", "Data Analysis", "Data Science", "Statistics",
    "Power BI", "Tableau", "Excel",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git",
    "React", "Node.js", "Django", "Flask", "FastAPI",
    "REST API", "MongoDB", "PostgreSQL", "MySQL",
]


def extract_skills(text: str) -> list[str]:
    """Find which known skills appear in a block of free text (resume or job description)."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for skill in SKILL_VOCABULARY:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def calculate_match_score(resume_skills: list[str], job_skills: list[str]) -> dict:
    """
    Deterministic match score: overlap between resume skills and job
    required skills. Used as the no-LLM fallback and as the fast path
    for scoring many jobs at once (an LLM call per job would be slow
    and expensive at scale).
    """
    if not job_skills:
        # No structured skills on the job — fall back to resume skill count
        # as a weak signal so the score isn't always zero.
        score = min(len(resume_skills) * 5, 60)
        return {"score": score, "matched_skills": [], "missing_skills": []}

    resume_set = {s.lower() for s in resume_skills}
    job_set = {s.lower() for s in job_skills}

    matched = [s for s in job_skills if s.lower() in resume_set]
    missing = [s for s in job_skills if s.lower() not in resume_set]

    overlap_ratio = len(matched) / len(job_set) if job_set else 0
    score = round(overlap_ratio * 100)

    return {
        "score": score,
        "matched_skills": matched,
        "missing_skills": missing,
    }

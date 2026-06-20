"""
Resume Section Editor agent.

Improves just the PROFILE/SUMMARY section of a resume to match a target
job description. This existed in the original codebase but was never
called from app.py — now it's wired into the Resume Tailor page as a
lighter-weight alternative to a full rewrite.
"""
from __future__ import annotations

from core.llm_provider import LLMUnavailableError, generate_text

_SYSTEM_PROMPT = "You are an ATS Resume Optimizer."

_PROMPT_TEMPLATE = """Improve the PROFILE section only.

Rules:
- Keep it 3-4 lines.
- ATS friendly.
- Match the job description.
- Do not invent fake experience.
- Do not add fake skills.

Current Profile:
{profile_text}

Job Description:
{job_description}

Return ONLY the improved profile text.
"""


def improve_profile(profile_text: str, job_description: str) -> str:
    """Raises LLMUnavailableError if no provider is configured."""
    prompt = _PROMPT_TEMPLATE.format(profile_text=profile_text, job_description=job_description)
    response = generate_text(prompt, system=_SYSTEM_PROMPT, max_tokens=300)
    return response.text

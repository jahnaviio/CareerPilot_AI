"""
Cover Letter Generator agent.

The original implementation (in two duplicated, broken files) never
actually generated a cover letter — it returned a hardcoded test string.
This is a real implementation: LLM-backed when a provider is configured,
with a clean template fallback so the feature still produces something
usable with zero AI setup.
"""
from __future__ import annotations

from core.llm_provider import LLMUnavailableError, generate_text, is_llm_available

_SYSTEM_PROMPT = (
    "You are an expert career writer helping a student write a concise, "
    "genuine cover letter for an internship application."
)

_PROMPT_TEMPLATE = """Write a concise, professional cover letter (max 300 words) for an
internship application.

Candidate's Resume:
{resume_text}

Company: {company_name}
Role: {role_name}

Rules:
- Do not invent experience not present in the resume.
- Sound genuine and specific to the role, not generic.
- 3-4 short paragraphs: opening hook, relevant strengths, why this company/role, closing.
- Return only the letter body — no subject line, no notes.
"""

_FALLBACK_TEMPLATE = """Dear Hiring Team at {company_name},

I am writing to express my interest in the {role_name} position. Based on my
background and the skills I've developed, I believe I would be a strong fit
for this opportunity and am excited about the chance to contribute to your team.

I would welcome the opportunity to discuss how my experience aligns with
your needs. Thank you for considering my application.

Sincerely,
A motivated candidate

[Note: This is a template letter. Configure an LLM provider (LLM_PROVIDER
in your .env) to generate a personalized letter based on your resume.]
"""


def generate_cover_letter(resume_text: str, company_name: str, role_name: str) -> str:
    if not is_llm_available():
        return _FALLBACK_TEMPLATE.format(company_name=company_name, role_name=role_name)

    prompt = _PROMPT_TEMPLATE.format(
        resume_text=resume_text, company_name=company_name, role_name=role_name
    )
    try:
        response = generate_text(prompt, system=_SYSTEM_PROMPT, max_tokens=600)
        return response.text
    except LLMUnavailableError:
        return _FALLBACK_TEMPLATE.format(company_name=company_name, role_name=role_name)

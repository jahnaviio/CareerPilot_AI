"""
Resume Tailor agent.

Rewrites a resume's Summary/Skills/Experience/Projects sections to better
match a target job description, while preserving factual details
(name, education, certifications, contact info, achievements).

Requires an LLM provider — rewriting prose well is not something the
rule-based fallback can do meaningfully, so this raises LLMUnavailableError
if no provider is configured. Callers (UI layer) should catch this and
show a clear setup message rather than a stack trace.
"""
from __future__ import annotations

from core.llm_provider import LLMUnavailableError, generate_text  # noqa: F401  (re-exported for callers)

_SYSTEM_PROMPT = "You are an expert ATS Resume Optimizer."

_PROMPT_TEMPLATE = """TASK:
- Rewrite the resume according to the job description.
- Keep the resume SHORT.
- Keep it within ONE PAGE.
- Do NOT add fake experience.
- Do NOT add fake projects.
- Keep the candidate's name, education, certifications, contact details and achievements.
- Only improve:
  - Summary
  - Skills
  - Projects descriptions
  - Experience descriptions

Resume:
{resume_text}

Job Description:
{job_description}

Output a clean ATS-friendly resume.
Avoid unnecessary explanations.
Do not write notes or comments.
Return only the final resume content.
"""


def tailor_resume(resume_text: str, job_description: str) -> str:
    """Returns the tailored resume text. Raises LLMUnavailableError if no provider is configured."""
    prompt = _PROMPT_TEMPLATE.format(resume_text=resume_text, job_description=job_description)
    response = generate_text(prompt, system=_SYSTEM_PROMPT, max_tokens=2500)
    return response.text

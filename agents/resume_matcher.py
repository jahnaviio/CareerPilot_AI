"""
Resume Matcher agent.

Compares a resume against a job description. Uses the configured LLM
provider for rich qualitative feedback (strengths, gaps, suggestions);
falls back to the deterministic skill-overlap scorer in
agents/skill_matcher.py when no LLM is configured, so this feature works
even with zero AI setup.
"""
from __future__ import annotations

from dataclasses import dataclass

from agents.skill_matcher import calculate_match_score, extract_skills
from core.llm_provider import LLMUnavailableError, generate_text, is_llm_available

_SYSTEM_PROMPT = (
    "You are an expert career advisor helping a student evaluate their fit "
    "for an internship. Be specific, honest, and constructive."
)


@dataclass
class MatchAnalysis:
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    ai_feedback: str | None  # None when no LLM provider is configured
    source: str  # "llm" or "rule_based"


def analyze_match(resume_text: str, job_description: str) -> MatchAnalysis:
    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_description)
    rule_result = calculate_match_score(resume_skills, job_skills)

    if not is_llm_available():
        return MatchAnalysis(
            score=rule_result["score"],
            matched_skills=rule_result["matched_skills"],
            missing_skills=rule_result["missing_skills"],
            ai_feedback=None,
            source="rule_based",
        )

    prompt = f"""Resume:
{resume_text}

Job Description:
{job_description}

Compare them and give a concise, well-organized response with these sections:
1. Match Score (0-100)
2. Strengths
3. Missing Skills
4. Suggestions to improve fit
"""
    try:
        response = generate_text(prompt, system=_SYSTEM_PROMPT)
        return MatchAnalysis(
            score=rule_result["score"],
            matched_skills=rule_result["matched_skills"],
            missing_skills=rule_result["missing_skills"],
            ai_feedback=response.text,
            source="llm",
        )
    except LLMUnavailableError:
        return MatchAnalysis(
            score=rule_result["score"],
            matched_skills=rule_result["matched_skills"],
            missing_skills=rule_result["missing_skills"],
            ai_feedback=None,
            source="rule_based",
        )

"""Pydantic schemas for the structured resume profile. Everything the LLM or heuristics produce is
validated against these, and every claim carries evidence copied from the resume text."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Skill(BaseModel):
    name: str
    category: str = "other"
    strength: Literal["demonstrated", "listed"] = "listed"   # demonstrated = appears in project/experience text
    evidence: list[str] = Field(default_factory=list)          # verbatim resume lines
    user_added: bool = False


class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    period: str = ""
    grade: str = ""
    evidence: list[str] = Field(default_factory=list)


class Project(BaseModel):
    title: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    organization: str = ""
    role: str = ""
    kind: Literal["internship", "job", "other"] = "other"
    period: str = ""
    bullets: list[str] = Field(default_factory=list)


class Certification(BaseModel):
    name: str
    issuer: str = ""


class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    links: list[str] = Field(default_factory=list)
    summary: str = ""
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    sections_detected: list[str] = Field(default_factory=list)
    graduation_year: Optional[int] = None
    experience_years_estimate: float = 0.0

    def skill_names(self) -> list[str]:
        return [s.name for s in self.skills]

    def skill_map(self) -> dict[str, Skill]:
        return {s.name.lower(): s for s in self.skills}


class LLMProfileEnrichment(BaseModel):
    """What we ask the LLM to return. Merged into the deterministic profile only after evidence checks."""
    summary: str = ""
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

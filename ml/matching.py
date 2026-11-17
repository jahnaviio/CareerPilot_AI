"""Hybrid opportunity matching.

score = 100 * ( 0.40 * skills + 0.30 * semantic + 0.15 * role_alignment + 0.15 * eligibility )   (weights: config.MATCH_WEIGHTS)

skills          demonstrated=1.0 / listed=0.6 / missing=0 over the skills the posting asks for (taxonomy match on the text)
semantic        0.6 * cos(profile, posting) + 0.4 * cos(best project, posting), calibrated by the embedding backend
role_alignment  your suitability (ml.roles) for the role family the posting title belongs to; 0.25 if none matches
eligibility     1.0 unless the posting asks for more years / a higher seniority / a PhD / a graduation year you do not meet;
                a hard mismatch caps the final score at 35
If a posting names no recognisable skills, the skills weight moves to semantic similarity (and that is stated in the result).
This is a transparent heuristic, not a validated probability of being hired."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from config import MATCH_WEIGHTS
from ml.embeddings import Embedder
from ml.roles import ROLES, RoleRecommendation, profile_text
from nlp.schemas import ResumeProfile

SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|head of|director|manager|vp|architect)\b", re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:or more\s*)?years?(?:'| of)?\s*(?:of\s*)?(?:relevant\s*|professional\s*|industry\s*|hands-on\s*)?(?:experience|exp)", re.I)
PHD = re.compile(r"\b(ph\.?d|doctorate)\b", re.I)
GRAD_YEAR = re.compile(r"(?:graduat\w+|class of|complete\w* (?:your )?(?:degree|studies))[^.\n]{0,40}?((?:20)\d{2})", re.I)
WORK_AUTH = re.compile(r"(authori[sz]ed to work|work authori[sz]ation|right to work|must (?:currently )?(?:reside|be located) in)", re.I)


@dataclass
class MatchResult:
    score: float
    components: dict[str, float | None]
    matched_skills: list[str]
    weak_skills: list[str]
    missing_skills: list[str]
    required_skills: list[str]
    relevant_projects: list[dict]
    role_family: str
    concerns: list[str]
    improvements: list[str]
    weights_used: dict[str, float]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _role_family(title: str) -> str | None:
    t = title.lower()
    best, best_len = None, 0
    for r in ROLES:
        for kw in r.keywords:
            if kw.strip() in t and len(kw) > best_len:
                best, best_len = r.key, len(kw)
    return best


def eligibility(p: ResumeProfile, title: str, text: str, is_internship: bool) -> tuple[float, list[str], bool]:
    concerns: list[str] = []
    elig, hard = 1.0, False
    if SENIOR.search(title) and not is_internship:
        concerns.append("The title signals a senior or lead role; this is likely above entry level.")
        elig, hard = min(elig, 0.1), True
    ym = [int(m.group(1)) for m in YEARS.finditer(text)]
    if ym and not is_internship:
        need = min(ym)
        gap = need - p.experience_years_estimate
        if gap >= 3:
            concerns.append(f"Asks for {need}+ years of experience; your resume shows about {p.experience_years_estimate:g}.")
            elig, hard = min(elig, 0.15), True
        elif gap > 1:
            concerns.append(f"Asks for {need}+ years of experience; your resume shows about {p.experience_years_estimate:g}.")
            elig = min(elig, 0.55)
    if PHD.search(text) and not any("ph" in (e.degree or "").lower() for e in p.education):
        required = re.search(r"(ph\.?d|doctorate)[^.\n]{0,40}(required|must|pursuing|currently)|(required|pursuing|currently)[^.\n]{0,40}(ph\.?d|doctorate)", text, re.I)
        if required:
            concerns.append("Mentions a PhD as required or expected.")
            elig = min(elig, 0.4)
    gy = {int(m.group(1)) for m in GRAD_YEAR.finditer(text)}
    if gy and p.graduation_year and p.graduation_year not in gy:
        concerns.append(f"Posting mentions graduation year(s) {', '.join(map(str, sorted(gy)))}; your resume suggests {p.graduation_year}.")
        elig = min(elig, 0.5)
    if WORK_AUTH.search(text):
        concerns.append("Mentions work authorisation or residency requirements - check you are eligible before applying.")
        elig = min(elig, 0.7)
    return elig, concerns, hard


def match_opportunity(p: ResumeProfile, roles: list[RoleRecommendation], embedder: Embedder, *, title: str, description: str,
                      required_skills: list[str], is_internship: bool, profile_vec: np.ndarray | None = None,
                      project_vecs: list[tuple[str, np.ndarray]] | None = None, job_vec: np.ndarray | None = None) -> MatchResult:
    skills = p.skill_map()
    matched, weak, missing = [], [], []
    got = 0.0
    for r in required_skills:
        s = skills.get(r.lower())
        if s is None:
            missing.append(r)
        elif s.strength == "demonstrated":
            matched.append(r); got += 1.0
        else:
            matched.append(r); weak.append(r); got += 0.6
    skill_c = got / len(required_skills) if required_skills else None

    doc = f"{title}\n{description[:3500]}"
    if profile_vec is None:
        profile_vec = embedder.encode([profile_text(p) or " "])[0]
    if job_vec is None:
        job_vec = embedder.encode([doc])[0]
    cos_all = float(profile_vec @ job_vec)
    best_proj, proj_list = 0.0, []
    for name, v in (project_vecs or []):
        c = float(v @ job_vec)
        proj_list.append({"project": name, "similarity": round(c, 3)})
    proj_list.sort(key=lambda x: -x["similarity"])
    if proj_list:
        best_proj = proj_list[0]["similarity"]
    sem_raw = 0.6 * cos_all + 0.4 * best_proj if proj_list else cos_all
    sem = embedder.calibrated(sem_raw)

    fam = _role_family(title)
    role_score = {r.key: r.score for r in roles}
    align = role_score[fam] / 100 if fam else 0.25

    elig, concerns, hard = eligibility(p, title, description, is_internship)

    w = dict(MATCH_WEIGHTS)
    notes = []
    if skill_c is None:
        w["semantic"] += w.pop("skills"); w["skills"] = 0.0
        notes.append("This posting doesn't list specific skills, so the score relies more on how well its wording fits your resume.")
        skill_c_used = 0.0
    else:
        skill_c_used = skill_c
    score = 100 * (w["skills"] * skill_c_used + w["semantic"] * sem + w["role_alignment"] * align + w["eligibility"] * elig)
    if hard:
        score = min(score, 35.0)
        notes.append("Score capped because the posting appears to require more experience or seniority than your resume shows.")
    if not embedder.is_semantic:
        notes.append(f"Semantic similarity uses the lightweight '{embedder.name}' backend (lexical, not deep semantic). Install sentence-transformers for full semantic matching.")

    improvements = [f"Learn or demonstrate {m}: it is requested in the posting and absent from your resume." for m in missing[:3]]
    improvements += [f"Show {w_} in a project or internship bullet (currently only listed under skills)." for w_ in weak[:2]]
    return MatchResult(round(score, 1), {"skills": None if skill_c is None else round(skill_c, 2), "semantic": round(sem, 2),
                                          "role_alignment": round(align, 2), "eligibility": round(elig, 2), "raw_cosine": round(cos_all, 3)},
                       matched, weak, missing, required_skills, proj_list[:2], fam or "", concerns, improvements[:4], w, notes)


def project_texts(p: ResumeProfile) -> list[tuple[str, str]]:
    return [(pr.title, f"{pr.title}. {pr.description} {' '.join(pr.technologies)}") for pr in p.projects if pr.title]

"""Builds a validated ResumeProfile: deterministic extraction first (always available), then optional
LLM enrichment whose output is accepted only if its evidence is found in the resume text."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from core.llm.base import LLMError, LLMProvider
from core.security import detect_injection, wrap_untrusted
from nlp.schemas import (Certification, Education, Experience, LLMProfileEnrichment, Project,
                         ResumeProfile, Skill)
from nlp.sections import BULLET, split_sections
from nlp.skills import category_of, skills_with_evidence

log = logging.getLogger(__name__)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,11}\d(?!\d)")
URL = re.compile(r"(?:https?://|www\.)[^\s,;|)]+|(?:github\.com|linkedin\.com/in|gitlab\.com)/[^\s,;|)]+", re.I)
DEGREE = re.compile(r"\b(b\.?\s?tech|b\.?\s?e\b|b\.?\s?sc|bca|bachelor[^,\n]*|m\.?\s?tech|m\.?\s?sc|mca|mba|master[^,\n]*|ph\.?d|diploma|intermediate|ssc|hsc|class (x|xii))\b", re.I)
YEAR_RANGE = re.compile(r"((?:19|20)\d{2})\s*[-–—to ]+\s*((?:19|20)\d{2}|present|current|ongoing)", re.I)
INSTITUTION = re.compile(r"[^,\n|]*(university|institute|college|school|academy|iit|nit)[^,\n|]*", re.I)


def build_profile(text: str, llm: LLMProvider | None = None) -> tuple[ResumeProfile, str, list[str]]:
    """Returns (profile, method, warnings)."""
    warnings: list[str] = []
    profile = _deterministic(text)
    method = "deterministic"
    if detect_injection(text):
        warnings.append("Some text in this file looked unusual (like instructions rather than resume content). It was ignored.")
    if llm is not None:
        try:
            enr = llm.complete_json(
                LLMProfileEnrichment,
                "You extract structured data from a resume. Copy facts only from the resume. Never invent employers, dates, "
                "numbers, projects, certifications or skills. Leave fields empty when not stated. Keep descriptions as written.",
                "Extract summary, education, projects (title, description, technologies, bullets), experience (organization, role, "
                "kind=internship|job|other, period, bullets), certifications and achievements.\n\n" + wrap_untrusted("resume", text))
            profile = _merge_enrichment(profile, enr, text)
            method = f"deterministic+{llm.name}"
        except LLMError as exc:
            warnings.append("We read your resume with our standard method.")
    profile = _finalise(profile, text)
    return profile, method, warnings


# ---------------- deterministic ----------------
def _deterministic(text: str) -> ResumeProfile:
    secs = split_sections(text)
    header = secs.get("header", [])
    p = ResumeProfile(sections_detected=[k for k in secs if k != "header"])
    m = EMAIL.search(text)
    p.email = m.group(0) if m else ""
    pm = PHONE.search("\n".join(header[:8]))
    p.phone = pm.group(0).strip() if pm else ""
    p.links = list(dict.fromkeys(u.rstrip(".") for u in URL.findall(text)))[:8]
    p.name = _guess_name(header)
    p.summary = " ".join(secs.get("summary", []))[:600]
    p.education = _education(secs.get("education", []))
    p.projects = _projects(secs.get("projects", []))
    p.experience = _experience(secs.get("experience", []))
    p.certifications = [Certification(name=l[:160]) for l in secs.get("certifications", []) if len(l) > 3][:15]
    p.achievements = [l[:240] for l in secs.get("achievements", []) if len(l) > 5][:12]
    return p


def _guess_name(header: list[str]) -> str:
    for line in header[:4]:
        if EMAIL.search(line) or URL.search(line) or re.search(r"\d{5,}", line):
            continue
        if 2 <= len(line.split()) <= 5 and len(line) < 50 and not re.search(r"[|@:/]", line):
            return line.title() if line.isupper() else line
    return ""


def _education(lines: list[str]) -> list[Education]:
    out: list[Education] = []
    cur: Education | None = None
    for line in lines:
        inst = INSTITUTION.search(line)
        deg = DEGREE.search(line)
        yr = YEAR_RANGE.search(line) or re.search(r"(?:19|20)\d{2}", line)
        if inst and (cur is None or cur.institution):
            cur = Education(institution=inst.group(0).strip(" -–"), evidence=[line[:200]])
            out.append(cur)
        elif cur is None:
            cur = Education(evidence=[line[:200]]); out.append(cur)
        else:
            cur.evidence.append(line[:200])
        if deg and not cur.degree:
            cur.degree = line[:120]
        if yr and not cur.period:
            cur.period = yr.group(0)
        g = re.search(r"(cgpa|gpa|percentage)[:\s]*([\d.]+\s*(?:/\s*\d+)?%?)", line, re.I)
        if g and not cur.grade:
            cur.grade = g.group(2)
    return out[:5]


def _group_entries(lines: list[str]) -> list[list[str]]:
    """Group lines into entries: a new entry starts at a short non-bullet title line after content."""
    groups: list[list[str]] = []
    for line in lines:
        is_title = len(line) < 90 and not line.endswith(".") and not re.match(r"^(built|developed|designed|implemented|created|used|worked|led|integrated|deployed)\b", line, re.I)
        if is_title and (not groups or len(groups[-1]) > 1):
            groups.append([line])
        elif groups:
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def _projects(lines: list[str]) -> list[Project]:
    out = []
    for g in _group_entries(lines):
        title = re.split(r"\s[|–—-]\s|\(|:", g[0])[0].strip()[:120]
        body = g[1:]
        techs = skills_with_evidence([("projects", " ".join(g))])
        out.append(Project(title=title or g[0][:120], description=" ".join(body)[:500], bullets=[b[:240] for b in body][:6],
                           technologies=list(techs)[:12], links=URL.findall(" ".join(g))[:2]))
    return out[:10]


def _experience(lines: list[str]) -> list[Experience]:
    out = []
    for g in _group_entries(lines):
        head = g[0]
        period = (YEAR_RANGE.search(" ".join(g[:2])) or re.search(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}[^\n]{0,25}", " ".join(g[:2]), re.I))
        kind = "internship" if re.search(r"intern|trainee|apprentice", " ".join(g[:2]), re.I) else ("job" if re.search(r"engineer|developer|analyst|associate|manager|consultant", head, re.I) else "other")
        out.append(Experience(organization="", role=head[:140], kind=kind, period=period.group(0) if period else "", bullets=[b[:240] for b in g[1:]][:6]))
    return out[:8]


# ---------------- LLM merge with evidence verification ----------------
def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def _supported(snippet: str, text_norm: str) -> bool:
    """A claim is accepted only if its key words appear in the resume text (anti-hallucination guard)."""
    words = [w for w in _norm(snippet).split() if len(w) > 3]
    if not words:
        return False
    hit = sum(1 for w in words if w in text_norm)
    return hit / len(words) >= 0.8


def _merge_enrichment(base: ResumeProfile, enr: LLMProfileEnrichment, text: str) -> ResumeProfile:
    tn = _norm(text)
    if enr.summary and _supported(enr.summary, tn):
        base.summary = enr.summary[:600]
    good_projects = [p for p in enr.projects if _supported(p.title, tn)]
    if good_projects:
        for p in good_projects:  # drop technologies not actually present in the text
            p.technologies = [t for t in p.technologies if _norm(t) in tn]
            p.bullets = [b for b in p.bullets if _supported(b, tn)]
        base.projects = good_projects[:10]
    good_exp = [e for e in enr.experience if _supported(f"{e.role} {e.organization}", tn)]
    if good_exp:
        for e in good_exp:
            e.bullets = [b for b in e.bullets if _supported(b, tn)]
        base.experience = good_exp[:8]
    good_cert = [c for c in enr.certifications if _supported(c.name, tn)]
    if good_cert:
        base.certifications = good_cert[:15]
    good_ach = [a for a in enr.achievements if _supported(a, tn)]
    if good_ach:
        base.achievements = good_ach[:12]
    good_edu = [e for e in enr.education if _supported(f"{e.institution} {e.degree}", tn)]
    if good_edu:
        base.education = good_edu[:5]
    return base


# ---------------- finalisation: skills with evidence, estimates ----------------
def _finalise(p: ResumeProfile, text: str) -> ResumeProfile:
    secs = split_sections(text)
    tagged: list[tuple[str, str]] = []
    for sec, lines in secs.items():
        if sec in ("links",):
            continue
        for line in lines:
            if sec == "header" and (EMAIL.search(line) or URL.search(line)):
                continue  # contact lines are not skill evidence
            tagged.append((sec, line))
    found = skills_with_evidence(tagged)
    user_added = [s for s in p.skills if s.user_added]
    skills: list[Skill] = []
    for name, d in found.items():
        demo = bool(d["sections"] & {"projects", "experience", "achievements"})
        skills.append(Skill(name=name, category=category_of(name), strength="demonstrated" if demo else "listed", evidence=d["evidence"]))
    have = {s.name.lower() for s in skills}
    skills.extend(s for s in user_added if s.name.lower() not in have)
    p.skills = sorted(skills, key=lambda s: (s.strength != "demonstrated", s.category, s.name))
    years = [int(y) for e in p.education for y in re.findall(r"(?:19|20)\d{2}", e.period)]
    p.graduation_year = max(years) if years else None
    p.experience_years_estimate = _experience_years(p)
    return p


def _experience_years(p: ResumeProfile) -> float:
    total = 0.0
    now = datetime.now().year
    for e in p.experience:
        if e.kind == "internship":
            continue  # internships do not count as years of professional experience
        m = YEAR_RANGE.search(e.period or "")
        if m:
            start = int(m.group(1)); end = now if m.group(2).lower() in ("present", "current", "ongoing") else int(m.group(2))
            total += max(0, end - start)
    return float(total)

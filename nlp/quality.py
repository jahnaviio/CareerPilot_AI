"""Resume quality analysis. Deterministic rules; each issue says what/why/how and, where useful, an improved
example that uses [bracketed placeholders] - the tool never invents numbers or achievements for the user."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from nlp.schemas import ResumeProfile

WEAK_STARTS = ("worked on", "responsible for", "helped", "helping", "assisted", "involved in", "participated in", "did ", "made ", "handled", "tried", "learned")
STRONG_VERBS = "Built, Designed, Implemented, Developed, Automated, Optimised, Deployed, Reduced, Improved, Led, Analysed"
HAS_NUMBER = re.compile(r"\d")
BULLET_CHARS = re.compile(r"^\s*([•\-\*–·▪●◦➢])")


@dataclass
class Issue:
    id: str
    severity: str  # high | medium | low
    what: str
    why: str
    how: str
    example: str = ""
    lines: list[str] = field(default_factory=list)


def _all_bullets(p: ResumeProfile) -> list[str]:
    out = []
    for pr in p.projects:
        out += pr.bullets or ([pr.description] if pr.description else [])
    for e in p.experience:
        out += e.bullets
    return [b for b in out if b]


def analyse_quality(p: ResumeProfile, raw_text: str) -> dict:
    issues: list[Issue] = []
    secs = set(p.sections_detected)
    words = len(raw_text.split())

    for sec, label, sev in (("education", "Education", "high"), ("skills", "Skills", "high"), ("projects", "Projects", "high")):
        if sec not in secs:
            issues.append(Issue(f"missing_{sec}", sev, f"No clear '{label}' section was detected.",
                                "Recruiters and ATS parsers look for standard section headings.",
                                f"Add a section titled exactly '{label}'."))
    if "experience" not in secs and "projects" in secs:
        issues.append(Issue("missing_experience", "low", "No Experience/Internships section detected.",
                            "For students this is fine if projects are strong, but any internship or club work helps.",
                            "If you have any internship, freelance, club or volunteer work, add it under 'Experience'."))
    if not p.email:
        issues.append(Issue("no_email", "high", "No email address found.", "Recruiters need a way to contact you.", "Add a professional email in the header."))
    if not any("github" in l.lower() for l in p.links):
        issues.append(Issue("no_github", "medium", "No GitHub link found.", "For technical roles, code is the best proof of your skills.",
                            "Add your GitHub profile or project repository links."))
    if not any("linkedin" in l.lower() for l in p.links):
        issues.append(Issue("no_linkedin", "low", "No LinkedIn link found.", "Many recruiters check LinkedIn before replying.", "Add your LinkedIn URL."))

    bullets = _all_bullets(p)
    weak = [b for b in bullets if b.lower().startswith(WEAK_STARTS)]
    if weak:
        issues.append(Issue("weak_verbs", "medium", f"{len(weak)} bullet(s) start with weak phrases.",
                            "Strong action verbs show ownership and impact.",
                            f"Start bullets with verbs like: {STRONG_VERBS}.",
                            "Instead of 'Worked on a chatbot', write 'Built a chatbot using [tools] that [what it does / result]'.", weak[:3]))
    no_num = [b for b in bullets if not HAS_NUMBER.search(b)]
    if bullets and len(no_num) / len(bullets) > 0.7:
        issues.append(Issue("no_metrics", "high", "Most bullets contain no measurable detail.",
                            "Numbers (size, speed, accuracy, users, time saved) make claims credible.",
                            "Add real figures you can back up: dataset size, accuracy/F1, response time, number of users or test cases. "
                            "If you have no number, describe scope instead (e.g. 'across 3 modules').",
                            "Built a RAG assistant with ChromaDB and FastAPI, [add the number of documents or the accuracy you measured].",
                            no_num[:3]))
    long_b = [b for b in bullets if len(b.split()) > 35]
    if long_b:
        issues.append(Issue("long_bullets", "medium", f"{len(long_b)} bullet(s) are longer than 35 words.",
                            "Long bullets are skimmed or skipped.", "Split each into two lines: what you built, then the result or tool.", lines=long_b[:2]))
    thin = [pr.title for pr in p.projects if len((pr.description or " ".join(pr.bullets)).split()) < 12]
    if thin:
        issues.append(Issue("thin_projects", "high", f"Project(s) with very little description: {', '.join(thin[:3])}.",
                            "A title alone does not show what you did or which skills you used.",
                            "For each project give: the problem, your approach and tools, and the outcome.",
                            "[Project name] – Built [what] using [tech] to [problem]; [result or scope]."))
    no_tech = [pr.title for pr in p.projects if not pr.technologies]
    if no_tech:
        issues.append(Issue("no_tech_named", "medium", f"Project(s) without recognisable technologies: {', '.join(no_tech[:3])}.",
                            "Keyword matching (ATS and recruiters) depends on named tools.", "Name the languages, libraries and platforms used in each project."))
    listed_only = [s.name for s in p.skills if s.strength == "listed" and s.category in ("ai_ml", "framework", "language")]
    if len(listed_only) >= 4:
        issues.append(Issue("unproven_skills", "medium", f"{len(listed_only)} technical skills appear only in the Skills list: {', '.join(listed_only[:6])}.",
                            "Skills with no project or experience behind them look like keyword padding.",
                            "Mention the ones you really know in a project or internship bullet, or remove the ones you cannot discuss in an interview."))
    if words < 150:
        issues.append(Issue("too_short", "medium", f"The resume is very short ({words} words).", "There may not be enough to judge your skills.", "Add project details and relevant coursework."))
    elif words > 900:
        issues.append(Issue("too_long", "medium", f"The resume is long ({words} words).", "Entry-level resumes work best on one page.", "Cut older or low-relevance items and shorten bullets."))
    kinds = {BULLET_CHARS.match(l).group(1) for l in raw_text.splitlines() if BULLET_CHARS.match(l)}
    if len(kinds) > 2:
        issues.append(Issue("inconsistent_bullets", "low", f"{len(kinds)} different bullet styles are used.", "Inconsistent formatting looks careless.", "Use one bullet style throughout."))
    sloppy = [l.strip() for l in raw_text.splitlines() if re.search(r"\b(\w+) \1\b", l, re.I) or re.match(r"^\s*[a-z]{3,}\s+\w+", l) and l.strip().endswith(".") and l.strip()[0].islower()]
    if sloppy:
        issues.append(Issue("grammar", "low", "Possible repeated words or lowercase sentence starts.", "Small writing slips reduce trust.", "Proofread the flagged lines.", lines=sloppy[:3]))
    if re.search(r"\bI\b|\bmy\b", " ".join(bullets), re.I):
        issues.append(Issue("first_person", "low", "Bullets use first-person words (I / my).", "Resumes conventionally omit pronouns.", "Remove 'I' and 'my' from bullet points."))

    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: order[i.severity])
    penalty = sum({"high": 12, "medium": 6, "low": 2}[i.severity] for i in issues)
    return {"issues": [i.__dict__ for i in issues], "checks_run": 14, "readiness_points": max(0, 100 - penalty),
            "score_note": "This is a to-do list for your resume, not a prediction of how recruiters will respond.",
            "word_count": words}

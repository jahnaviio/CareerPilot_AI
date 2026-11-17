"""Deterministic analyses built on the validated profile: skill-gap, roadmap, readiness, skill buckets."""
from __future__ import annotations

from math import ceil

from ml.roles import ROLE_BY_KEY, RoleRecommendation
from nlp.schemas import ResumeProfile
from services.resources import project_for, resources_for


def skill_buckets(p: ResumeProfile, target_role: str | None = None) -> dict:
    demo = [s for s in p.skills if s.strength == "demonstrated"]
    listed = [s for s in p.skills if s.strength == "listed"]
    strong = [s for s in demo if len(s.evidence) >= 1]
    limited = [s for s in p.skills if s.strength == "listed" or (s.strength == "demonstrated" and len(s.evidence) < 1)]
    out = {
        "identified": [s.name for s in p.skills],
        "strong_evidence": [{"name": s.name, "evidence": s.evidence[:2]} for s in strong],
        "limited_evidence": [{"name": s.name, "note": "Listed under skills but not shown in any project or experience bullet."} for s in listed],
        "missing_for_target": [],
        "to_improve": [s.name for s in listed if s.category in ("ai_ml", "framework", "language")][:8],
    }
    if target_role and target_role in ROLE_BY_KEY:
        r = ROLE_BY_KEY[target_role]
        have = p.skill_map()
        out["missing_for_target"] = [x for x in (*r.core, *r.preferred) if x.lower() not in have]
    return out


def skill_gap(p: ResumeProfile, role_key: str) -> dict:
    role = ROLE_BY_KEY[role_key]
    have = p.skill_map()
    existing, gaps = [], []
    for group, level in ((role.core, "core"), (role.preferred, "preferred")):
        for sk in group:
            s = have.get(sk.lower())
            if s is not None and s.strength == "demonstrated":
                existing.append({"skill": sk, "level": level, "status": "demonstrated"})
                continue
            if s is not None:
                priority, status = ("medium" if level == "core" else "low"), "listed only"
                why = f"{sk} is a {level} skill for {role.title}. It is on your resume but not backed by a project or internship."
            else:
                priority, status = ("high" if level == "core" else "medium"), "missing"
                why = f"{sk} is a {level} skill for {role.title} and does not appear on your resume."
            gaps.append({"skill": sk, "level": level, "status": status, "priority": priority, "why": why,
                         "resources": resources_for(sk), "project": project_for(sk)})
    order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (order[g["priority"]], g["level"] != "core"))
    return {"role_key": role_key, "role_title": role.title, "existing": existing, "gaps": gaps}


def roadmap(p: ResumeProfile, role_key: str, days: int, quality_issues: list[dict] | None = None) -> dict:
    assert days in (30, 60, 90)
    weeks = {30: 4, 60: 8, 90: 12}[days]
    gap = skill_gap(p, role_key)
    focus = [g for g in gap["gaps"] if g["priority"] in ("high", "medium")] or gap["gaps"]
    plan = []
    wk = 1
    # one focus skill per week; high-priority first. A skill already demonstrated is never scheduled.
    for g in focus:
        if wk > weeks - 1:
            break
        verb = "Show" if g["status"] == "listed only" else "Learn"
        title = f"Show {g['skill']} in a real project" if verb == "Show" else f"Learn {g['skill']}"
        plan.append({"week": wk, "title": title, "objective": f"Be able to explain and use {g['skill']} in a working project.",
                     "topics": [f"Core concepts of {g['skill']}", f"How {g['skill']} is used in {gap['role_title']} work", "Common mistakes and how to test your work"],
                     "assignment": f"Work through the official material, then complete a small exercise on {g['skill']}.",
                     "project": g["project"], "outcome": f"One GitHub project and one resume bullet that shows {g['skill']}.",
                     "resources": g["resources"], "skill": g["skill"]})
        wk += 1
    fixes = [i for i in (quality_issues or []) if i["severity"] in ("high", "medium")][:2]
    filler = [
        ("Strengthen your resume evidence", "Make your existing work easier to believe.",
         [f["what"] for f in fixes] or ["Add the tools used and a real result to each project"], "Rewrite your project bullets using real results; do not add claims you cannot defend.",
         "Resume v2 with measurable, truthful bullets."),
        ("Apply and iterate", "Turn the new skills into applications.",
         ["Shortlist 10 matching postings", "Tailor your resume honestly for each", "Track every application in CareerPilot"],
         "Send applications to the best-matching opportunities.", "A set of submitted applications and notes on responses."),
    ]
    i = 0
    while wk <= weeks:
        t, o, topics, a, out = filler[i % len(filler)]
        plan.append({"week": wk, "title": t, "objective": o, "topics": topics, "assignment": a, "project": "", "outcome": out, "resources": [], "skill": ""})
        wk += 1; i += 1
    return {"role_key": role_key, "role_title": gap["role_title"], "days": days, "weeks": plan,
            "note": "Skills you already demonstrate are not scheduled. Timeline assumes roughly 6-8 focused hours per week."}


def readiness(roles: list[RoleRecommendation]) -> dict:
    ready = [r for r in roles if r.tier == "ready"]
    close = [r for r in roles if r.tier == "close"]
    prep = [r for r in roles if r.tier == "needs_work"]
    top = roles[0] if roles else None
    next_skills: dict[str, int] = {}
    for r in roles[:4]:
        for m in r.missing_core:
            next_skills[m] = next_skills.get(m, 0) + 1
    return {"ready_now": [(r.title, r.score) for r in ready], "close": [(r.title, r.score) for r in close],
            "needs_preparation": [(r.title, r.score) for r in prep[:5]],
            "most_important_next": [s for s, _ in sorted(next_skills.items(), key=lambda x: -x[1])][:5],
            "top_role": top.title if top else "",
            "disclaimer": "These are heuristic estimates from your resume. They do not predict whether any employer will shortlist or select you."}

from __future__ import annotations

import streamlit as st

from config import settings
from ml.roles import ROLES, ROLE_BY_KEY
from nlp.schemas import Certification, Education, Project, ResumeProfile, Skill
from nlp.skills import TAXONOMY, category_of
from ui.components import bar, chips, empty_state, esc, md, notice, page_header, score_ring, stat
from ui.state import get_app

TIER = {"ready": ("Strong fit", "good"), "close": ("Close", "blue"), "needs_work": ("Needs preparation", "warn")}


def render(user) -> None:
    app = get_app()
    r, profile = app.load(user.id)
    if r is None:
        _landing(user, app)
        return
    page_header("Resume Intelligence", "What your resume shows, which roles it supports, and what to improve next.", "Page 1")
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    with c1:
        md(f'<div class="cp-card" style="margin:0"><div class="cp-title">{esc(r.filename)}</div>'
           f'<div class="cp-sub">Uploaded {esc(r.created_at.strftime("%d %b %Y"))} · {len(profile.skills)} skills · {len(profile.projects)} projects · '
           f'{"edited by you" if r.user_edited else "read from your resume automatically"}</div></div>')
    with c2:
        with st.popover("Replace resume", use_container_width=True):
            _uploader(user, app, key="replace")
    if profile.skills and not any(s.strength == "demonstrated" for s in profile.skills) and not profile.projects:
        notice("No projects or experience were detected, so every skill counts as “listed only”. Check the Profile tab and correct anything we missed.", "warn")
    t_roles, t_quality, t_skills, t_plan, t_profile = st.tabs(["Career roles", "Resume quality", "Skills", "Gap & roadmap", "Profile & corrections"])
    with t_roles:
        _roles(user, app, r)
    with t_quality:
        _quality(user, app, r)
    with t_skills:
        _skills(user, app, r, profile)
    with t_plan:
        _plan(user, app, r)
    with t_profile:
        _profile(user, app, r, profile)


# ---------------- landing / upload ----------------
def _landing(user, app) -> None:
    md('<div class="cp-hero"><div class="cp-eyebrow" style="color:#9FA8FF">Resume Intelligence</div>'
       '<h1>Start with your resume</h1><p>We extract your skills and projects, show which roles they support, review the resume like a recruiter would, '
       'and use the result to rank real internships and jobs.</p></div>')
    _uploader(user, app, key="first")
    md('<div class="cp-steps"><div class="cp-step"><b>Evidence-based</b><span>Each skill links to the line of your resume that shows it.</span></div>'
       '<div class="cp-step"><b>Clear scoring</b><span>Every score comes with the reasons behind it.</span></div>'
       '<div class="cp-step"><b>You stay in control</b><span>Correct anything we misread, and delete your data any time.</span></div></div>')


def _uploader(user, app, key: str) -> None:
    f = st.file_uploader("Upload your resume (PDF or DOCX, up to %d MB)" % settings.max_upload_mb, type=["pdf", "docx"], key=f"up_{key}")
    if f is not None and st.button("Analyse resume", type="primary", key=f"go_{key}"):
        with st.spinner("Reading your resume…"):
            res = app.analyse_resume(user.id, f.name, f.getvalue())
        if res.error:
            notice(res.error, "error")
            return
        for w in res.warnings:
            notice(w, "warn")
        st.session_state["flash"] = "We already had this exact file, so we reused the existing analysis." if res.reused else "Resume analysed. Check the details and correct anything we misread."
        st.rerun()


# ---------------- roles ----------------
def _roles(user, app, r) -> None:
    roles = app.roles(user.id, r.id)
    rd = app.readiness(user.id, r.id)
    if (m := st.session_state.pop("flash", None)):
        notice(m, "success")
    c = st.columns(3)
    c[0].markdown(stat(len(rd["ready_now"]), "roles you’re ready for"), unsafe_allow_html=True)
    c[1].markdown(stat(len(rd["close"]), "roles that are close"), unsafe_allow_html=True)
    c[2].markdown(stat(rd["top_role"] or "—", "your strongest match"), unsafe_allow_html=True)
    st.write("")
    with st.expander("How is the suitability score calculated?"):
        st.markdown(
            "**Your score is made of four parts:** the must-have skills for the role (45%), the nice-to-have skills (15%), how well your projects and work show those skills (15%), and how closely your resume wording fits the role (25%).\n\n"
            "- A skill you used in a project or internship counts fully. A skill that is only listed counts 60%. A missing skill counts 0.\n"
            "- The role requirements are typical ones chosen for this app.\n\n"
            "The score is a guide to help you decide what to work on next. It does **not** predict whether a company will select you.")
    for rec in roles[:5]:
        _role_card(rec)
    with st.expander(f"All {len(roles)} roles"):
        for rec in roles[5:]:
            _role_card(rec, compact=True)
    notice(rd["disclaimer"], "info")


def _role_card(rec, compact: bool = False) -> None:
    label, kind = TIER[rec.tier]
    md(f'<div class="cp-card"><div class="cp-row"><div><div class="cp-title">{esc(rec.title)}</div>'
       f'<span class="cp-chip {kind}">{label}</span><div class="cp-sub" style="margin-top:6px">{esc(rec.explanation)}</div></div>'
       f'<div>{score_ring(rec.score, 58, rec.title)}</div></div></div>')
    if compact:
        return
    with st.expander("Why this score and what to do next", expanded=False):
        cc = rec.components
        for lab, k in (("Must-have skills", "core_skills"), ("Nice-to-have skills", "preferred_skills"), ("Shown in your projects or work", "evidence"), ("Resume wording match", "semantic")):
            bar(cc[k] * 100, lab, f"{cc[k] * 100:.0f}%")
        if rec.matching_skills:
            md('<div class="cp-section-label">Skills you already have for this role</div>' + chips(rec.matching_skills, "good"))
        if rec.missing_core or rec.missing_preferred:
            md('<div class="cp-section-label">Missing or weak</div>' + chips(rec.missing_core, "bad") + chips(rec.missing_preferred[:6], "warn") + chips([f"{x} (listed only)" for x in rec.limited_evidence], "warn"))
        if rec.evidence:
            md('<div class="cp-section-label">Resume evidence</div>')
            for e in rec.evidence[:4]:
                st.caption(f"**{e['skill']}** — “{e['line']}”")
        if rec.next_steps:
            md('<div class="cp-section-label">Recommended next steps</div>')
            for s in rec.next_steps:
                st.markdown(f"- {s}")


# ---------------- quality ----------------
def _quality(user, app, r) -> None:
    q = app.quality(user.id, r.id)
    issues = q["issues"]
    high = sum(1 for i in issues if i["severity"] == "high")
    c = st.columns(3)
    c[0].markdown(stat(len(issues), "things to improve"), unsafe_allow_html=True)
    c[1].markdown(stat(high, "high priority"), unsafe_allow_html=True)
    c[2].markdown(stat(q["word_count"], "words"), unsafe_allow_html=True)
    st.caption(q["score_note"])
    if not issues:
        notice("No issues found by the automatic checks. A human review is still worthwhile.", "success")
    kind = {"high": "bad", "medium": "warn", "low": "neutral"}
    for i in issues:
        with st.expander(f"{i['what']}", expanded=i["severity"] == "high"):
            md(chip_html(i["severity"].title() + " priority", kind[i["severity"]]))
            st.markdown(f"**Why it matters:** {i['why']}")
            st.markdown(f"**How to improve:** {i['how']}")
            if i["example"]:
                st.markdown(f"**Example (fill in your real details):** {i['example']}")
            for l in i["lines"]:
                st.caption(f"From your resume: “{l[:200]}”")


def chip_html(label, kind):
    return f'<span class="cp-chip {kind}">{esc(label)}</span>'


# ---------------- skills ----------------
def _skills(user, app, r, profile) -> None:
    roles = app.roles(user.id, r.id)
    from services.analysis import skill_buckets
    target = st.selectbox("Target role", [x.key for x in ROLES], index=[x.key for x in ROLES].index(roles[0].key), format_func=lambda k: ROLE_BY_KEY[k].title, key="skills_role")
    b = skill_buckets(profile, target)
    c = st.columns(2)
    with c[0]:
        md('<div class="cp-section-label">Backed by project or experience evidence</div>')
        if b["strong_evidence"]:
            for s in b["strong_evidence"]:
                with st.expander(s["name"]):
                    for e in s["evidence"]:
                        st.caption(f"“{e}”")
        else:
            st.caption("None yet. Describe your projects with the tools you used.")
        md('<div class="cp-section-label">Limited evidence (listed only)</div>')
        md(chips([s["name"] for s in b["limited_evidence"]], "warn") or '<span class="cp-sub">None</span>')
    with c[1]:
        md('<div class="cp-section-label">All identified skills</div>' + chips(b["identified"], "neutral"))
        md('<div class="cp-section-label">Missing for ' + esc(ROLE_BY_KEY[target].title) + '</div>' + (chips(b["missing_for_target"], "bad") or '<span class="cp-sub">Nothing missing from the role profile.</span>'))
        md('<div class="cp-section-label">Worth strengthening</div>' + (chips(b["to_improve"], "blue") or '<span class="cp-sub">None</span>'))
    st.caption("A skill mentioned in a resume is not the same as a skill demonstrated in real work. We separate the two.")


# ---------------- gap & roadmap ----------------
def _plan(user, app, r) -> None:
    roles = app.roles(user.id, r.id)
    keys = [x.key for x in ROLES]
    c1, c2 = st.columns([2, 1])
    role_key = c1.selectbox("Target role", keys, index=keys.index(roles[0].key), format_func=lambda k: ROLE_BY_KEY[k].title, key="plan_role")
    days = c2.radio("Roadmap length", [30, 60, 90], horizontal=True, format_func=lambda d: f"{d} days", key="plan_days")
    gap = app.skill_gap(user.id, r.id, role_key)
    md('<div class="cp-section-label">Skill gap</div>')
    if gap["existing"]:
        md("<span class='cp-sub'>Already demonstrated:</span> " + chips([e["skill"] for e in gap["existing"]], "good"))
    if not gap["gaps"]:
        notice("You demonstrate every skill in this role profile.", "success")
    for g in gap["gaps"]:
        k = {"high": "bad", "medium": "warn", "low": "neutral"}[g["priority"]]
        with st.expander(f"{g['skill']}  ·  {g['priority'].title()} priority  ·  {g['status']}"):
            st.markdown(g["why"])
            st.markdown(f"**Practical project:** {g['project']}")
            for res in g["resources"]:
                st.markdown(f"- [{res['title']}]({res['url']}) (official site)")
    st.divider()
    rm = app.roadmap(user.id, r.id, role_key, days)
    prog = app.roadmap_progress(user.id, r.id, role_key, days)
    total = sum(3 if w["project"] else 2 for w in rm["weeks"])
    done = sum(1 for v in prog.values() if v)
    md(f'<div class="cp-section-label">{days}-day roadmap — {esc(rm["role_title"])}</div>')
    bar(100 * done / max(1, total), "Progress", f"{done} of {total} tasks")
    st.caption(rm["note"])
    for w in rm["weeks"]:
        with st.expander(f"Week {w['week']} · {w['title']}", expanded=w["week"] == 1):
            st.markdown(f"**Objective:** {w['objective']}")
            tasks = [("topics", "Study: " + "; ".join(w["topics"])), ("assignment", "Assignment: " + w["assignment"])]
            if w["project"]:
                tasks.append(("project", "Project: " + w["project"]))
            for tid, text in tasks:
                key = f"w{w['week']}:{tid}"
                val = st.checkbox(text, value=prog.get(key, False), key=f"{role_key}{days}{key}")
                if val != prog.get(key, False):
                    app.set_roadmap_task(user.id, r.id, role_key, days, key, val)
                    st.rerun()
            st.markdown(f"**Expected outcome:** {w['outcome']}")
            for res in w["resources"]:
                st.markdown(f"- [{res['title']}]({res['url']})")


# ---------------- profile corrections ----------------
def _profile(user, app, r, p: ResumeProfile) -> None:
    st.caption("Correct anything we misread. Changes refresh your roles, quality review and matches.")
    with st.form("profile_form"):
        c = st.columns(3)
        name = c[0].text_input("Name", p.name)
        email = c[1].text_input("Email", p.email)
        phone = c[2].text_input("Phone", p.phone)
        summary = st.text_area("Summary", p.summary, height=90)
        links = st.text_area("Links (one per line)", "\n".join(p.links), height=70)
        have = {s.name: s for s in p.skills}
        picked = st.multiselect("Skills", sorted(set(TAXONOMY) | set(have)), default=list(have), help="Remove skills that are wrong; add ones we missed.")
        st.markdown("**Education**")
        edu = st.data_editor([{"institution": e.institution, "degree": e.degree, "period": e.period, "grade": e.grade} for e in p.education] or [{"institution": "", "degree": "", "period": "", "grade": ""}],
                             num_rows="dynamic", use_container_width=True, key="edu_ed")
        st.markdown("**Projects**")
        proj = st.data_editor([{"title": x.title, "description": x.description, "technologies": ", ".join(x.technologies)} for x in p.projects] or [{"title": "", "description": "", "technologies": ""}],
                              num_rows="dynamic", use_container_width=True, key="proj_ed")
        certs = st.text_area("Certifications (one per line)", "\n".join(c.name for c in p.certifications), height=80)
        if st.form_submit_button("Save corrections", type="primary"):
            new = p.model_copy(deep=True)
            new.name, new.email, new.phone, new.summary = name.strip(), email.strip(), phone.strip(), summary.strip()
            new.links = [l.strip() for l in links.splitlines() if l.strip()]
            new.skills = [have[s] if s in have else Skill(name=s, category=category_of(s), strength="listed", user_added=True) for s in picked]
            new.education = [Education(institution=e.get("institution") or "", degree=e.get("degree") or "", period=e.get("period") or "", grade=e.get("grade") or "") for e in edu if any((e.get("institution"), e.get("degree")))]
            new.projects = [Project(title=x["title"], description=x.get("description") or "", technologies=[t.strip() for t in (x.get("technologies") or "").split(",") if t.strip()], bullets=[x["description"]] if x.get("description") else [])
                            for x in proj if (x.get("title") or "").strip()]
            new.certifications = [Certification(name=c.strip()) for c in certs.splitlines() if c.strip()]
            if app.update_profile(user.id, r.id, new):
                st.session_state["flash"] = "Profile updated. Roles and matches will refresh."
                st.rerun()
    with st.expander("Resume retention and deletion"):
        st.caption(f"Resumes are kept for {settings.resume_retention_days} days, then removed automatically. You can delete this resume now.")
        if st.button("Delete this resume and its analysis", key="del_resume"):
            from core.db import session_scope
            from repositories import resumes as rr
            with session_scope(app.factory) as s:
                rr.delete_resume(s, user.id, r.id)
            app.store.delete("resume", {"user_id": user.id, "resume_id": r.id})
            st.session_state["flash"] = "Resume deleted."
            st.rerun()

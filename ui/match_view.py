"""Shared rendering for match details, explanations, apply flow and AI assist (used by Opportunities and Saved)."""
from __future__ import annotations

import streamlit as st

from core.db import session_scope
from repositories import applications as apps
from repositories import opportunities as orepo
from services.workflow import FeatureUnavailable, QuotaExceeded
from ui.components import bar, chips, esc, md, notice
from utils.export import docx_bytes, pdf_bytes


def match_details(m: dict) -> None:
    c = m["components"]
    labels = {"skills": "Skills", "semantic": "Resume wording match", "role_alignment": "Role fit", "eligibility": "Requirements you meet"}
    w = m.get("weights_used", {})
    for k, lab in labels.items():
        v = c.get(k)
        if v is None:
            bar(0, lab, "not scored (no skills named)")
        else:
            bar(v * 100, lab, f"{v * 100:.0f}% · weight {w.get(k, 0) * 100:.0f}%")
    if m["matched_skills"]:
        md('<div class="cp-section-label">Skills you already have</div>' + chips(m["matched_skills"], "good"))
    if m["weak_skills"]:
        md('<div class="cp-section-label">Listed on your resume but not demonstrated</div>' + chips(m["weak_skills"], "warn"))
    if m["missing_skills"]:
        md('<div class="cp-section-label">Requested but missing</div>' + chips(m["missing_skills"], "bad"))
    for p in m.get("relevant_projects", []):
        st.caption(f"Closest project: **{p['project']}**")
    for c_ in m.get("concerns", []):
        notice(c_, "warn")
    for n in m.get("notes", []):
        if "backend" not in n:
            st.caption(n)
    if m.get("improvements"):
        md('<div class="cp-section-label">How to improve your fit</div>')
        for i in m["improvements"]:
            st.markdown(f"- {i}")
    st.caption("The match score looks at your skills, how closely your resume wording fits the posting, the type of role, and the requirements you meet. It is a guide, not a promise of selection.")


def explanation(app, user, resume_id: int, o, key: str) -> None:
    ck = f"expl_{key}_{o.id}"
    if st.button("Explain this match using my resume", key=f"btn_{ck}"):
        with st.spinner("Finding the most relevant parts of your resume and this posting…"):
            try:
                st.session_state[ck] = app.explain_match(user.id, resume_id, o.id)
            except PermissionError:
                notice("Match details are not available yet.", "error")
    out = st.session_state.get(ck)
    if not out:
        return
    if out.get("llm_error"):
        notice("Showing a simple summary.", "warn")
    if out.get("summary"):
        st.markdown(out["summary"])
    passages = out.get("passages", {})
    for title, items, kind in (("Your strengths", out.get("strengths", []), "good"), ("Gaps to close", out.get("gaps", []), "warn")):
        if items:
            md(f'<div class="cp-section-label">{title}</div>')
            for c in items:
                st.markdown(f"- {c['text']}")
    if out.get("next_steps"):
        md('<div class="cp-section-label">Next steps</div>')
        for s in out["next_steps"]:
            st.markdown(f"- {s}")
    with st.expander("Parts of your resume and the posting we looked at"):
        for k, t in passages.items():
            st.caption(f"**{'Your resume' if k.startswith('R') else 'The posting'}** — {t}")


@st.dialog("Did you complete your application?")
def confirm_applied_dialog(app, user_id: int, opp_id: int) -> None:
    with session_scope(app.factory) as s:
        o = orepo.get(s, opp_id)
        title, company = o.title, o.company
    st.write(f"**{title}** at **{company}**")
    st.caption("CareerPilot never submits applications for you. Only confirm if you finished applying on the employer’s site.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, I applied", type="primary", use_container_width=True):
        with session_scope(app.factory) as s:
            apps.confirm_applied(s, user_id, orepo.get(s, opp_id))
        st.session_state["flash_page"] = "Marked as Applied in your tracker."
        st.rerun()
    if c2.button("Not yet", use_container_width=True):
        with session_scope(app.factory) as s:
            apps.ensure_interested(s, user_id, orepo.get(s, opp_id))
        st.session_state["flash_page"] = "Added to your tracker as Interested."
        st.rerun()


def ai_assist(app, user, resume_id: int, o) -> None:
    with st.popover("Writing help"):
        st.caption("Uses only what is on your resume and in this posting.")
        for kind, label in (("tailor", "Tailor resume for this role"), ("cover", "Generate cover letter")):
            if st.button(label, key=f"{kind}_{o.id}", use_container_width=True):
                with st.spinner("Writing…"):
                    try:
                        fn = app.tailor_resume if kind == "tailor" else app.cover_letter
                        st.session_state[f"{kind}_out_{o.id}"] = fn(user.id, resume_id, o.id)
                    except FeatureUnavailable:
                        notice("This feature isn't available right now. Please try again later.", "warn")
                    except QuotaExceeded as e:
                        notice(str(e), "warn")
        for kind, label in (("tailor", "Tailored resume"), ("cover", "Cover letter")):
            out = st.session_state.get(f"{kind}_out_{o.id}")
            if out:
                md(f'<div class="cp-section-label">{label} (review before use)</div>')
                if out["warning"]:
                    notice(out["warning"], "warn")
                txt = st.text_area(label, out["text"], height=240, key=f"ta_{kind}_{o.id}", label_visibility="collapsed")
                c = st.columns(3)
                c[0].download_button("DOCX", docx_bytes(txt), f"{kind}_{o.id}.docx", key=f"d1_{kind}_{o.id}")
                c[1].download_button("PDF", pdf_bytes(txt), f"{kind}_{o.id}.pdf", key=f"d2_{kind}_{o.id}")
                c[2].download_button("TXT", txt, f"{kind}_{o.id}.txt", key=f"d3_{kind}_{o.id}")


def apply_button(o) -> None:
    if o.status != "open":
        st.caption("Application link unavailable: this listing is no longer confirmed by its source.")
    elif o.link_kind == "aggregator":
        st.link_button("Apply via Adzuna ↗", o.apply_url, type="primary", use_container_width=True,
                       help="Adzuna is a job-search website. The link opens the posting there, and you apply through it.")
    elif o.apply_url_verified:
        st.link_button("Apply on Official Website ↗", o.apply_url, type="primary", use_container_width=True)
    else:
        st.caption("Application link could not be verified as official.")

from __future__ import annotations

import streamlit as st
from sqlalchemy import func, select

from core.db import session_scope
from core.models import Opportunity
from repositories import applications as apps
from repositories import opportunities as orepo
from ui import match_view
from ui.components import chip, empty_state, esc, md, notice, opportunity_card_html, page_header
from ui.state import get_app


def render(user) -> None:
    app = get_app()
    page_header("Saved Opportunities", "Everything you’ve shortlisted, jobs and internships together.", "Page 3")
    if (m := st.session_state.pop("flash_page", None)):
        notice(m, "success")
    f = st.segmented_control("Show", ["All", "Internships", "Jobs"], default="All", key="saved_filter", label_visibility="collapsed") or "All"
    flt = None if f == "All" else (f == "Internships")
    r, _ = app.load(user.id)
    with session_scope(app.factory) as s:
        rows = orepo.list_saved(s, user.id, flt)
        matches = orepo.matches_for(s, user.id, r.id) if r else {}
        tracked = {a.opportunity_id for a in apps.list_for_user(s, user.id) if a.opportunity_id}
    if not rows:
        empty_state("Nothing saved yet", "Save internships and jobs from the Opportunities page and they will appear here.")
        return
    st.caption(f"{len(rows)} saved")
    for o, sv in rows:
        m_ = ({"score": matches[o.id].score, **matches[o.id].detail} if o.id in matches else None)
        md(opportunity_card_html(o, m_))
        c = st.columns([2, 1, 1, 1])
        with c[0]:
            match_view.apply_button(o)
        with c[1]:
            if o.id in tracked:
                st.button("In tracker ✓", key=f"tk_{o.id}", disabled=True, use_container_width=True)
            elif st.button("Track", key=f"tk_{o.id}", use_container_width=True):
                with session_scope(app.factory) as s:
                    apps.ensure_interested(s, user.id, o)
                st.rerun()
        with c[2]:
            if st.button("I applied…", key=f"ap_{o.id}", use_container_width=True):
                match_view.confirm_applied_dialog(app, user.id, o.id)
        with c[3]:
            if st.button("Remove", key=f"rm_{o.id}", use_container_width=True):
                with session_scope(app.factory) as s:
                    orepo.remove_saved(s, user.id, o.id)
                st.rerun()
        with st.expander("Company and match details"):
            with session_scope(app.factory) as s:
                n_open = s.scalar(select(func.count()).select_from(Opportunity).where(Opportunity.company == o.company, Opportunity.status == "open")) or 0
            st.markdown(f"**{o.company}** · {n_open} open listing(s) in CareerPilot · source: `{o.source_key}`")
            st.markdown(f"[Original posting ↗]({o.posting_url})")
            if m_:
                match_view.match_details(m_)
            else:
                st.caption("Upload a resume to see how this listing matches.")
        if st.button("Not interested anymore", key=f"ni_{o.id}", type="tertiary"):
            with session_scope(app.factory) as s:
                orepo.set_not_interested(s, user.id, o.id)
            st.rerun()

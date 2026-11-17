from __future__ import annotations

from datetime import date, datetime, timezone

import streamlit as st

from core.db import session_scope
from core.security import is_safe_external_url
from repositories import applications as apps
from ui.components import chip, empty_state, esc, fmt_date, md, notice, page_header, stat
from ui.state import get_app

COLORS = {"Interested": "#94A3B8", "Applied": "#2F6BFF", "Assessment": "#9A6FF5", "Interview": "#E5A100", "Offer": "#12805C", "Rejected": "#C2410C"}
CHIP = {"Interested": "neutral", "Applied": "blue", "Assessment": "accent", "Interview": "warn", "Offer": "good", "Rejected": "bad"}


def _dt(d: date | None):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) if d else None


@st.dialog("Delete this application?")
def _confirm_delete(app, user_id: int, app_id: int) -> None:
    st.write("This removes it from your tracker. This cannot be undone.")
    c = st.columns(2)
    if c[0].button("Delete", type="primary", use_container_width=True):
        with session_scope(app.factory) as s:
            apps.delete(s, user_id, app_id)
        st.rerun()
    if c[1].button("Cancel", use_container_width=True):
        st.rerun()


def render(user) -> None:
    app = get_app()
    page_header("Application Tracker", "Follow every application from first interest to outcome. You decide when something counts as applied.", "Page 4")
    if (m := st.session_state.pop("flash_page", None)):
        notice(m, "success")
    now = datetime.now(timezone.utc)
    with session_scope(app.factory) as s:
        apps.sync_follow_up_notifications(s, user.id, now)
        rows = apps.list_for_user(s, user.id)
        counts = apps.counts(s, user.id)
        notes = apps.unread_notifications(s, user.id)
    for n in notes:
        c = st.columns([6, 1], vertical_alignment="center")
        with c[0]:
            notice(n.message, "warn")
        if c[1].button("Dismiss", key=f"dn_{n.id}"):
            with session_scope(app.factory) as s:
                apps.mark_notification_read(s, user.id, n.id)
            st.rerun()
    total = sum(counts.values())
    if total:
        seg = "".join(f'<i style="width:{100 * counts[k] / total:.1f}%;background:{COLORS[k]}" title="{k}: {counts[k]}"></i>' for k in counts if counts[k])
        md(f'<div class="cp-stack" role="img" aria-label="Applications by status">{seg}</div>')
        cols = st.columns(len(counts))
        for c, k in zip(cols, counts):
            c.markdown(stat(counts[k], k), unsafe_allow_html=True)
        st.write("")
    with st.expander("Add an application manually"):
        with st.form("add_app", clear_on_submit=True):
            c = st.columns(3)
            company = c[0].text_input("Company")
            role = c[1].text_input("Role")
            status = c[2].selectbox("Status", apps.STATUSES)
            url = st.text_input("Listing URL (optional)")
            notes = st.text_area("Notes", height=70)
            if st.form_submit_button("Add", type="primary"):
                if not company.strip() or not role.strip():
                    notice("Company and role are required.", "warn")
                elif url.strip() and not is_safe_external_url(url.strip()):
                    notice("Enter a valid https:// link or leave it empty.", "warn")
                else:
                    with session_scope(app.factory) as s:
                        apps.create_manual(s, user.id, company, role, status, url.strip(), notes)
                    st.rerun()
    if not rows:
        empty_state("No applications yet", "Track a saved listing, or confirm an application from the Opportunities page. Nothing is added automatically.")
        return
    c = st.columns([2, 2])
    sel = c[0].multiselect("Status", apps.STATUSES, default=list(apps.STATUSES), label_visibility="collapsed", placeholder="Filter by status")
    q = c[1].text_input("Search", placeholder="Search company or role", label_visibility="collapsed")
    shown = [a for a in rows if a.status in sel and (not q or q.lower() in f"{a.company} {a.role}".lower())]
    st.caption(f"{len(shown)} of {len(rows)} applications")
    if not shown:
        empty_state("No matches", "Change the status filter or search to see more.")
    for a in shown:
        link = f' · <a href="{esc(a.listing_url)}" target="_blank" rel="noopener noreferrer">Listing ↗</a>' if a.listing_url and is_safe_external_url(a.listing_url) else ""
        dates = " · ".join(x for x in (f"Applied {fmt_date(a.applied_on)}" if a.applied_on else "", f"Interview {fmt_date(a.interview_on)}" if a.interview_on else "", f"Follow up {fmt_date(a.follow_up_on)}" if a.follow_up_on else "") if x)
        md(f'<div class="cp-card"><div class="cp-row"><div><div class="cp-title">{esc(a.role)}</div><div class="cp-sub">{esc(a.company)}{link}</div>'
           f'<div class="cp-sub" style="margin-top:4px">{esc(dates)}</div></div><div>{chip(a.status, CHIP[a.status])}</div></div></div>')
        with st.expander("Edit"):
            with st.form(f"edit_{a.id}"):
                c = st.columns(4)
                status = c[0].selectbox("Status", apps.STATUSES, index=apps.STATUSES.index(a.status))
                applied = c[1].date_input("Applied on", value=a.applied_on.date() if a.applied_on else None)
                interview = c[2].date_input("Interview on", value=a.interview_on.date() if a.interview_on else None)
                follow = c[3].date_input("Follow up on", value=a.follow_up_on.date() if a.follow_up_on else None)
                notes = st.text_area("Notes", a.notes, height=80)
                c2 = st.columns([1, 1, 4])
                save = c2[0].form_submit_button("Save", type="primary")
                delete = c2[1].form_submit_button("Delete")
            if save:
                with session_scope(app.factory) as s:
                    apps.update(s, user.id, a.id, status=status, applied_on=_dt(applied), interview_on=_dt(interview), follow_up_on=_dt(follow), notes=notes)
                st.rerun()
            if delete:
                _confirm_delete(app, user.id, a.id)

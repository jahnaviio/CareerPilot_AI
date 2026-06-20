"""Application Tracker page: the Applied / Interview / Rejected / Offer pipeline."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import app_config
from core.database import db_session
from repositories import application_repository
from repositories.application_repository import VALID_STATUSES
from ui.components.cards import empty_state


def render() -> None:
    st.title("Application Tracker")
    st.caption("Track every application from Applied to Offer.")

    with st.expander("➕ Add an application manually"):
        with st.form("add_application_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                company = st.text_input("Company")
            with c2:
                role = st.text_input("Role")
            with c3:
                status = st.selectbox("Status", VALID_STATUSES)
            notes = st.text_area("Notes (optional)", height=80)

            if st.form_submit_button("Add Application", type="primary"):
                if company.strip() and role.strip():
                    with db_session() as conn:
                        application_repository.create_application(
                            conn,
                            user_id=app_config.default_user_id,
                            company=company.strip(),
                            role=role.strip(),
                            status=status,
                            notes=notes.strip(),
                        )
                    st.success("Application added.")
                    st.rerun()
                else:
                    st.warning("Company and role are required.")

    st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)

    with db_session() as conn:
        applications = application_repository.list_applications(conn, app_config.default_user_id)
        counts = application_repository.count_by_status(conn, app_config.default_user_id)

    if not applications:
        empty_state(
            "No applications tracked yet",
            "Mark a job as Applied from the Internship Finder page, or add one manually above.",
            icon="📋",
        )
        return

    cols = st.columns(4)
    for col, status in zip(cols, VALID_STATUSES):
        with col:
            st.metric(status, counts.get(status, 0))

    st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)

    status_filter = st.multiselect("Filter by status", VALID_STATUSES, default=list(VALID_STATUSES))
    filtered = [a for a in applications if a.status in status_filter]

    st.subheader(f"Applications ({len(filtered)})")

    for app in filtered:
        cols = st.columns([3, 2, 2, 2, 2])
        with cols[0]:
            st.markdown(f"**{app.role}**")
            st.caption(app.company)
        with cols[1]:
            st.caption(f"Applied: {app.applied_at[:10]}")
        with cols[2]:
            new_status = st.selectbox(
                "Status",
                VALID_STATUSES,
                index=VALID_STATUSES.index(app.status),
                key=f"status_{app.id}",
                label_visibility="collapsed",
            )
            if new_status != app.status:
                with db_session() as conn:
                    application_repository.update_status(conn, app.id, new_status)
                st.rerun()
        with cols[3]:
            if app.notes:
                st.caption(app.notes[:60])
        with cols[4]:
            if st.button("Delete", key=f"delete_{app.id}"):
                with db_session() as conn:
                    application_repository.delete_application(conn, app.id)
                st.rerun()

    st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)
    with st.expander("📊 View as table"):
        df = pd.DataFrame(
            [
                {
                    "Company": a.company,
                    "Role": a.role,
                    "Status": a.status,
                    "Applied": a.applied_at[:10],
                    "Notes": a.notes,
                }
                for a in filtered
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

"""Notifications page: new jobs today, high matches, recommended opportunities feed."""
from __future__ import annotations

import streamlit as st

from config import app_config
from core.database import db_session
from repositories import notification_repository
from ui.components.cards import empty_state

_TYPE_ICONS = {
    "new_job": "🆕",
    "high_match": "🎯",
    "status_change": "📌",
    "system": "ℹ️",
}


def render() -> None:
    st.title("Notifications")
    st.caption("New jobs, high matches, and recommended opportunities.")

    with db_session() as conn:
        unread_count = notification_repository.count_unread(conn, app_config.default_user_id)

        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(f"{unread_count} unread" if unread_count else "All caught up")
        with col2:
            if unread_count and st.button("Mark all read"):
                with db_session() as write_conn:
                    notification_repository.mark_all_read(write_conn, app_config.default_user_id)
                st.rerun()

        notifications = notification_repository.list_notifications(conn, app_config.default_user_id, limit=50)

        if not notifications:
            empty_state(
                "No notifications yet",
                "Refresh jobs on the Internship Finder page to generate new alerts.",
                icon="🔔",
            )
            return

        for note in notifications:
            icon = _TYPE_ICONS.get(note.type, "🔔")
            with st.container():
                cols = st.columns([6, 1])
                with cols[0]:
                    weight = "**" if not note.is_read else ""
                    st.markdown(f"{icon} {weight}{note.title}{weight}")
                    if note.body:
                        st.caption(note.body)
                    st.caption(note.created_at[:16])
                with cols[1]:
                    if not note.is_read and st.button("Read", key=f"read_{note.id}"):
                        with db_session() as write_conn:
                            notification_repository.mark_read(write_conn, note.id)
                        st.rerun()
                st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)

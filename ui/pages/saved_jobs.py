"""Saved Jobs page: jobs the student bookmarked for later."""
from __future__ import annotations

import streamlit as st

from config import app_config
from core.database import db_session
from repositories import saved_job_repository
from ui.components.cards import empty_state, job_card


def render() -> None:
    st.title("Saved Jobs")
    st.caption("Internships you bookmarked to revisit later.")

    with db_session() as conn:
        saved = saved_job_repository.list_saved_jobs(conn, app_config.default_user_id)

    if not saved:
        empty_state(
            "No saved jobs yet",
            "Click 'Save' on any job in the Internship Finder page to bookmark it here.",
            icon="💾",
        )
        return

    for job in saved:
        job_card(company=job.company, role=job.role, skills=job.required_skills, location=job.location)
        if st.button("Remove", key=f"unsave_{job.id}"):
            with db_session() as conn:
                saved_job_repository.unsave_job(conn, app_config.default_user_id, job.id)
            st.rerun()

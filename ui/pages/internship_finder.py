"""Internship Finder page: browse stored jobs, trigger discovery from CSV seed + Remotive API."""
from __future__ import annotations

import streamlit as st

from config import SEED_INTERNSHIPS_CSV, app_config, job_config
from core.database import db_session
from repositories import application_repository, job_match_repository, job_repository, saved_job_repository
from services.ingestion_service import run_full_ingestion
from services.matching_service import recompute_matches_for_user
from services.notification_service import generate_notifications_for_user
from ui.components.cards import empty_state, job_card


def render() -> None:
    st.title("Internship Finder")
    st.caption(
        f"Live postings from Remotive (filtered for {', '.join(job_config.keywords[:5])}...) "
        "plus a curated seed list, all saved to your dashboard."
    )

    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("🔄 Refresh Jobs", type="primary"):
            with st.spinner("Discovering new internships..."):
                with db_session() as conn:
                    summary = run_full_ingestion(conn, str(SEED_INTERNSHIPS_CSV))
                    recompute_matches_for_user(conn, app_config.default_user_id)
                    generate_notifications_for_user(conn, app_config.default_user_id)

            st.success(
                f"Found {summary['total_new']} new internship(s) "
                f"({summary['new_from_remotive']} live, {summary['new_from_csv']} from seed list)."
            )
            st.rerun()

    st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)

    with db_session() as conn:
        search = st.text_input(
            "Search by company, role, or keyword", placeholder="e.g. Python, Google, Data Science"
        )
        sort_by_match = st.checkbox("Sort by match score", value=True)

        jobs = (
            job_repository.search_jobs(conn, search, limit=100)
            if search
            else job_repository.list_jobs(conn, limit=100)
        )

        if not jobs:
            empty_state(
                "No jobs found",
                "Click 'Refresh Jobs' above to pull in live internships.",
                icon="🔍",
            )
            return

        match_map = {}
        for job in jobs:
            match = job_match_repository.get_match(conn, app_config.default_user_id, job.id)
            if match:
                match_map[job.id] = match

        if sort_by_match and match_map:
            jobs.sort(
                key=lambda j: match_map[j.id].match_score if j.id in match_map else -1,
                reverse=True,
            )

        st.caption(f"Showing {len(jobs)} job(s)")

        for job in jobs:
            match = match_map.get(job.id)
            score = match.match_score if match else None
            skills = match.matched_skills if match else job.required_skills

            job_card(company=job.company, role=job.role, skills=skills, match_score=score, location=job.location)

            action_cols = st.columns([1, 1, 1, 3])
            with action_cols[0]:
                if job.url:
                    st.link_button("View Posting", job.url)
            with action_cols[1]:
                already_saved = saved_job_repository.is_saved(conn, app_config.default_user_id, job.id)
                label = "💾 Saved" if already_saved else "Save"
                if st.button(label, key=f"save_{job.id}", disabled=already_saved):
                    with db_session() as write_conn:
                        saved_job_repository.save_job(write_conn, app_config.default_user_id, job.id, score)
                    st.rerun()
            with action_cols[2]:
                if st.button("Mark Applied", key=f"apply_{job.id}"):
                    with db_session() as write_conn:
                        application_repository.create_application(
                            write_conn,
                            user_id=app_config.default_user_id,
                            company=job.company,
                            role=job.role,
                            job_id=job.id,
                        )
                    st.success(f"Marked '{job.role}' at {job.company} as Applied.")

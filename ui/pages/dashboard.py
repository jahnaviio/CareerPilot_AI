"""Dashboard home page."""
from __future__ import annotations

import streamlit as st

from config import app_config
from core.database import db_session
from repositories import job_repository
from services import notification_service, stats_service
from ui.components.cards import empty_state, job_card, stat_card


def render() -> None:
    st.title("Dashboard")
    st.caption("Your daily internship discovery and application command center.")

    with db_session() as conn:
        stats = stats_service.get_dashboard_stats(conn, app_config.default_user_id)

        cols = st.columns(4)
        with cols[0]:
            stat_card("Total Jobs Tracked", str(stats["total_jobs"]))
        with cols[1]:
            stat_card(
                "New Today",
                str(stats["new_jobs_today"]),
                delta="↑ fresh listings" if stats["new_jobs_today"] > 0 else None,
            )
        with cols[2]:
            stat_card("High Matches", str(stats["high_match_count"]), delta=f"≥{app_config.high_match_threshold}% fit")
        with cols[3]:
            stat_card("Applications Sent", str(stats["total_applications"]))

        if not stats["has_resume"]:
            st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)
            st.info(
                "📄 Upload a resume on the **Resumes** page to unlock personalized "
                "match scores and recommendations."
            )

        st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)

        rec_col, status_col = st.columns([2, 1])

        with rec_col:
            st.subheader("Recommended Opportunities")
            recommendations = notification_service.get_recommended_jobs(
                conn, app_config.default_user_id, limit=5
            )
            if not recommendations:
                empty_state(
                    "No recommendations yet",
                    "Upload a resume and refresh jobs to see your best matches here.",
                    icon="🎯",
                )
            else:
                for job, match in recommendations:
                    job_card(
                        company=job.company,
                        role=job.role,
                        skills=match.matched_skills or job.required_skills,
                        match_score=match.match_score,
                        location=job.location,
                    )

        with status_col:
            st.subheader("Application Pipeline")
            counts = stats["status_counts"]
            for status, count in counts.items():
                st.markdown(f"**{status}**")
                st.progress(
                    min(count / max(stats["total_applications"], 1), 1.0),
                    text=f"{count} application{'s' if count != 1 else ''}",
                )

        st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)
        st.subheader("Recently Discovered")
        recent_jobs = job_repository.list_jobs(conn, limit=5)
        if not recent_jobs:
            empty_state(
                "No jobs in your database yet",
                "Go to **Internship Finder** and click 'Refresh Jobs' to start discovering opportunities.",
                icon="🔍",
            )
        else:
            for job in recent_jobs:
                job_card(
                    company=job.company,
                    role=job.role,
                    skills=job.required_skills,
                    location=job.location,
                )

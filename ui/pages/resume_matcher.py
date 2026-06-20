"""Resume Matcher page: deep, qualitative AI analysis of resume fit against a job description."""
from __future__ import annotations

import streamlit as st

from agents.resume_matcher import analyze_match
from config import app_config
from core.database import db_session
from core.llm_provider import is_llm_available
from repositories import resume_repository
from ui.components.cards import empty_state, match_ring_svg


def render() -> None:
    st.title("Resume Matcher")
    st.caption("Paste a job description for a deep, qualitative match analysis.")

    with db_session() as conn:
        resume = resume_repository.get_active_resume(conn, app_config.default_user_id)

    if resume is None:
        empty_state("No active resume", "Upload a resume on the Resumes page first.", icon="📄")
        return

    if not is_llm_available():
        st.warning(
            "No AI provider configured — you'll get a skill-overlap score, but not "
            "qualitative AI feedback. Set `LLM_PROVIDER` and the relevant API key/host "
            "in your `.env` file to unlock full analysis."
        )

    job_description = st.text_area(
        "Job Description", height=220, placeholder="Paste the full job posting here..."
    )

    if st.button("Analyze Match", type="primary", disabled=not job_description.strip()):
        with st.spinner("Analyzing..."):
            analysis = analyze_match(resume.raw_text, job_description)

        ring_col, info_col = st.columns([1, 4])
        with ring_col:
            st.markdown(match_ring_svg(analysis.score, size=90), unsafe_allow_html=True)
        with info_col:
            if analysis.matched_skills:
                st.markdown("**Matched skills:** " + ", ".join(analysis.matched_skills))
            if analysis.missing_skills:
                st.markdown("**Missing skills:** " + ", ".join(analysis.missing_skills))

        if analysis.ai_feedback:
            st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)
            st.subheader("AI Analysis")
            st.markdown(analysis.ai_feedback)

"""Resumes page: upload, parse, and manage resumes (Resume Parser feature)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from agents.resume_parser import UnsupportedFileTypeError, parse_resume
from config import app_config
from core.database import db_session
from repositories import resume_repository
from services.matching_service import recompute_matches_for_user
from ui.components.cards import empty_state


def render() -> None:
    st.title("Resumes")
    st.caption("Upload your resume to power match scoring across every job in your dashboard.")

    uploaded_file = st.file_uploader("Upload a resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])

    if uploaded_file is not None:
        if st.button("Parse & Save Resume", type="primary"):
            with st.spinner("Parsing resume..."):
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                try:
                    parsed = parse_resume(tmp_path, uploaded_file.name)
                except UnsupportedFileTypeError as exc:
                    st.error(str(exc))
                    return
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

                if not parsed.raw_text:
                    st.error(
                        "Couldn't extract any text from that file. It may be a scanned "
                        "image PDF — try uploading a text-based PDF or DOCX instead."
                    )
                    return

                with db_session() as conn:
                    resume_repository.create_resume(
                        conn,
                        user_id=app_config.default_user_id,
                        filename=uploaded_file.name,
                        raw_text=parsed.raw_text,
                        extracted_skills=parsed.skills,
                    )
                    # New resume → old match scores are stale, recompute against everything.
                    recompute_matches_for_user(conn, app_config.default_user_id, only_new_jobs=False)

                st.success(f"Resume saved! Found {len(parsed.skills)} recognized skills.")
                st.rerun()

    st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)

    with db_session() as conn:
        resumes = resume_repository.list_resumes(conn, app_config.default_user_id)

        if not resumes:
            empty_state("No resumes yet", "Upload your first resume above to get started.", icon="📄")
            return

        st.subheader("Your Resumes")
        for resume in resumes:
            with st.expander(
                f"{'⭐ ' if resume.is_active else ''}{resume.filename} — {resume.created_at[:10]}",
                expanded=resume.is_active,
            ):
                st.markdown(f"**Status:** {'Active (used for matching)' if resume.is_active else 'Inactive'}")
                if resume.extracted_skills:
                    st.markdown("**Detected skills:** " + ", ".join(resume.extracted_skills))
                else:
                    st.markdown("**Detected skills:** None recognized — try a more detailed resume.")

                col1, col2 = st.columns([1, 4])
                with col1:
                    if not resume.is_active:
                        if st.button("Set Active", key=f"activate_{resume.id}"):
                            with db_session() as write_conn:
                                resume_repository.set_active_resume(
                                    write_conn, app_config.default_user_id, resume.id
                                )
                                recompute_matches_for_user(
                                    write_conn, app_config.default_user_id, only_new_jobs=False
                                )
                            st.rerun()

                with st.popover("Preview text"):
                    st.text(resume.raw_text[:2000] + ("..." if len(resume.raw_text) > 2000 else ""))

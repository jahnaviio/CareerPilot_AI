"""Cover Letter Generator page."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from agents.cover_letter_generator import generate_cover_letter
from config import app_config
from core.database import db_session
from repositories import resume_repository
from ui.components.cards import empty_state
from utils.docx_editor import create_docx


def render() -> None:
    st.title("Cover Letter Generator")
    st.caption("Generate a tailored cover letter from your active resume.")

    with db_session() as conn:
        resume = resume_repository.get_active_resume(conn, app_config.default_user_id)

    if resume is None:
        empty_state("No active resume", "Upload a resume on the Resumes page first.", icon="📄")
        return

    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input("Company Name", placeholder="e.g. OpenAI")
    with col2:
        role_name = st.text_input("Role Title", placeholder="e.g. AI Research Intern")

    ready = bool(company_name.strip() and role_name.strip())

    if st.button("Generate Cover Letter", type="primary", disabled=not ready):
        with st.spinner("Writing your cover letter..."):
            letter = generate_cover_letter(resume.raw_text, company_name, role_name)
        st.session_state["cover_letter_text"] = letter

    if "cover_letter_text" in st.session_state:
        st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)
        edited = st.text_area("Edit your letter", value=st.session_state["cover_letter_text"], height=350)

        if st.button("Generate DOCX"):
            with tempfile.TemporaryDirectory() as tmp_dir:
                out_path = Path(tmp_dir) / "Cover_Letter.docx"
                create_docx(edited, str(out_path))
                st.download_button(
                    "Download DOCX",
                    data=out_path.read_bytes(),
                    file_name="Cover_Letter.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )

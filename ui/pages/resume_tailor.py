"""Resume Tailor page: rewrite resume content to match a target job, with downloadable output."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from agents.resume_tailor import tailor_resume
from config import app_config
from core.database import db_session
from core.llm_provider import LLMUnavailableError, is_llm_available
from repositories import resume_repository
from ui.components.cards import empty_state
from utils.docx_editor import create_docx
from utils.pdf_generator import create_resume_pdf


def render() -> None:
    st.title("Resume Tailor")
    st.caption("Rewrite your Summary, Skills, and Experience sections to match a specific job.")

    with db_session() as conn:
        resume = resume_repository.get_active_resume(conn, app_config.default_user_id)

    if resume is None:
        empty_state("No active resume", "Upload a resume on the Resumes page first.", icon="📄")
        return

    if not is_llm_available():
        st.error(
            "Resume tailoring requires an AI provider. Set `LLM_PROVIDER=claude` "
            "(with `ANTHROPIC_API_KEY`) or `LLM_PROVIDER=ollama` in your `.env` file."
        )
        return

    job_description = st.text_area(
        "Target Job Description", height=200, placeholder="Paste the job posting you're applying to..."
    )

    if st.button("Tailor My Resume", type="primary", disabled=not job_description.strip()):
        with st.spinner("Tailoring resume — this can take a few seconds..."):
            try:
                tailored_text = tailor_resume(resume.raw_text, job_description)
            except LLMUnavailableError as exc:
                st.error(f"Couldn't generate a tailored resume: {exc}")
                return

        st.session_state["tailored_resume_text"] = tailored_text

    if "tailored_resume_text" in st.session_state:
        st.markdown("<hr class='cp-section-divider'/>", unsafe_allow_html=True)
        st.subheader("Tailored Resume")
        edited_text = st.text_area(
            "Review and edit before downloading", value=st.session_state["tailored_resume_text"], height=400
        )

        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            if st.button("Generate PDF"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    out_path = Path(tmp_dir) / "Tailored_Resume.pdf"
                    create_resume_pdf(edited_text, str(out_path))
                    st.download_button(
                        "Download PDF",
                        data=out_path.read_bytes(),
                        file_name="Tailored_Resume.pdf",
                        mime="application/pdf",
                    )
        with dl_col2:
            if st.button("Generate DOCX"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    out_path = Path(tmp_dir) / "Tailored_Resume.docx"
                    create_docx(edited_text, str(out_path))
                    st.download_button(
                        "Download DOCX",
                        data=out_path.read_bytes(),
                        file_name="Tailored_Resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )

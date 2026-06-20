"""Sidebar navigation for CareerPilot AI."""
from __future__ import annotations

import streamlit as st

from config import app_config
from core.database import db_session
from core.llm_provider import llm_config
from repositories import notification_repository

PAGES = {
    "Dashboard": "dashboard",
    "Resumes": "resumes",
    "Internship Finder": "internship_finder",
    "Resume Matcher": "resume_matcher",
    "Resume Tailor": "resume_tailor",
    "Cover Letter Generator": "cover_letter",
    "Application Tracker": "application_tracker",
    "Saved Jobs": "saved_jobs",
    "Notifications": "notifications",
}

_ICONS = {
    "Dashboard": "🏠",
    "Resumes": "📄",
    "Internship Finder": "🔍",
    "Resume Matcher": "🎯",
    "Resume Tailor": "✂️",
    "Cover Letter Generator": "✉️",
    "Application Tracker": "📋",
    "Saved Jobs": "💾",
    "Notifications": "🔔",
}


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            "<h2 style='color:#F1F0FA; margin-bottom:0;'>🚀 CareerPilot AI</h2>"
            "<p style='color:#A7A6C9; font-size:13px; margin-top:2px;'>"
            "Your internship co-pilot</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr style='border-color:#33345A;'/>", unsafe_allow_html=True)

        with db_session() as conn:
            unread = notification_repository.count_unread(conn, app_config.default_user_id)

        labels = []
        for name in PAGES:
            if name == "Notifications" and unread:
                labels.append(f"{_ICONS[name]} {name} ({unread})")
            else:
                labels.append(f"{_ICONS[name]} {name}")

        selected_label = st.radio("Navigate", labels, label_visibility="collapsed")
        selected_name = list(PAGES.keys())[labels.index(selected_label)]

        st.markdown("<hr style='border-color:#33345A;'/>", unsafe_allow_html=True)
        provider_label = {
            "claude": "Claude API",
            "ollama": "Ollama (local)",
            "none": "No AI configured",
        }.get(llm_config.provider, llm_config.provider)
        st.caption(f"AI provider: {provider_label}")

        return PAGES[selected_name]

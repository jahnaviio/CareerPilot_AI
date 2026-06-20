"""
CareerPilot AI — main entry point.

This file is intentionally thin: it configures the page, initializes the
database, injects the theme, renders the sidebar, and dispatches to the
selected page module. All business logic lives in services/ and agents/;
all data access lives in repositories/. Nothing here should grow beyond
routing.
"""
from __future__ import annotations

import streamlit as st

from core.database import init_db
from ui.pages import (
    application_tracker,
    cover_letter,
    dashboard,
    internship_finder,
    notifications,
    resume_matcher,
    resume_tailor,
    resumes,
    saved_jobs,
)
from ui.sidebar import render_sidebar
from ui.theme import inject_theme

st.set_page_config(
    page_title="CareerPilot AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
inject_theme()

_PAGE_RENDERERS = {
    "dashboard": dashboard.render,
    "resumes": resumes.render,
    "internship_finder": internship_finder.render,
    "resume_matcher": resume_matcher.render,
    "resume_tailor": resume_tailor.render,
    "cover_letter": cover_letter.render,
    "application_tracker": application_tracker.render,
    "saved_jobs": saved_jobs.render,
    "notifications": notifications.render,
}

selected_page = render_sidebar()
_PAGE_RENDERERS[selected_page]()

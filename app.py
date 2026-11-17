"""CareerPilot AI - entry point: theme, auth gate, four-page navigation."""
from __future__ import annotations

import streamlit as st

from config import settings
from services import auth
from ui import auth_view, theme
from ui.components import md, notice
from ui.pages import opportunities, resume_intelligence, saved, tracker
from ui.state import current_user, get_app, sign_out

st.set_page_config(page_title="CareerPilot AI", page_icon="◆", layout="wide", initial_sidebar_state="auto")
theme.inject()

PAGES = {"Resume Intelligence": resume_intelligence.render, "Opportunities": opportunities.render,
         "Saved Opportunities": saved.render, "Application Tracker": tracker.render}


def main() -> None:
    try:
        get_app()
    except Exception as exc:  # database not reachable / not migrated
        notice("Something went wrong while loading the app. Please refresh the page in a moment.", "error")
        if not settings.is_production:
            st.exception(exc)
        st.stop()
    user = current_user()
    if user is None:
        st.session_state.pop("token", None)
        auth_view.render()
        return
    with st.sidebar:
        md('<div class="cp-brand"><div class="cp-logo">C</div><div class="cp-brand-name">CareerPilot AI</div></div>')
        page = st.radio("Navigate", list(PAGES), label_visibility="collapsed", key="page")
        st.divider()
        md(f'<div class="cp-sb-note"><b style="color:#fff">{user.name or user.email}</b><br>{user.email}</div>')
        if st.button("Sign out", use_container_width=True):
            sign_out()
            st.rerun()
        with st.expander("Account & privacy"):
            st.caption("Your resume and results are private to your account. Deleting your account removes everything.")
            confirm = st.text_input("Type DELETE to enable account deletion", key="del_confirm")
            if st.button("Delete my account and data", disabled=confirm != "DELETE"):
                app = get_app()
                app.store.delete("resume", {"user_id": user.id})
                auth.delete_account(app.factory, user.id)
                sign_out()
                st.rerun()
    PAGES[page](user)


main()

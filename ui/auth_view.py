from __future__ import annotations

import streamlit as st

from services import auth
from ui.components import md, notice
from ui.state import get_app


def render() -> None:
    md('<div class="cp-hero"><div class="cp-eyebrow" style="color:#9FA8FF">CareerPilot AI</div>'
       '<h1>Understand your resume. Find real internships.</h1>'
       '<p>Upload your resume, see which roles fit and why, close your skill gaps, and apply through each employer’s official page. '
       'Every listing comes from a real employer job board.</p></div>')
    left, right = st.columns([1, 1], gap="large")
    app = get_app()
    with left:
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])
        with tab_in:
            with st.form("login"):
                email = st.text_input("Email", autocomplete="email")
                pw = st.text_input("Password", type="password", autocomplete="current-password")
                if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                    user, token, err = auth.login(app.factory, email, pw)
                    if err:
                        notice(err, "error")
                    else:
                        st.session_state["token"] = token
                        st.rerun()
        with tab_up:
            with st.form("register"):
                name = st.text_input("Name")
                email = st.text_input("Email", key="reg_email")
                pw = st.text_input("Password", type="password", key="reg_pw", help="At least 10 characters, mixed case, with a number.")
                agree = st.checkbox("I understand my resume is stored in my account and I can delete it at any time.")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    if not agree:
                        notice("Please confirm the privacy statement to continue.", "warn")
                    else:
                        user, err = auth.register(app.factory, email, name, pw)
                        if err:
                            notice(err, "error")
                        else:
                            u, token, e2 = auth.login(app.factory, email, pw)
                            st.session_state["token"] = token
                            st.rerun()
    with right:
        md('<div class="cp-steps" style="grid-template-columns:1fr">'
           '<div class="cp-step"><b>1 · Resume Intelligence</b><span>Structured profile, role fit, quality review, skill gaps and a 30/60/90-day plan.</span></div>'
           '<div class="cp-step"><b>2 · Opportunities</b><span>Verified internships and jobs from employer boards, ranked by how well they fit you.</span></div>'
           '<div class="cp-step"><b>3 · Saved &amp; 4 · Tracker</b><span>Save what you like and track every application you confirm.</span></div></div>')
        notice("Your resume stays private to your account. CareerPilot never applies on your behalf.", "info")

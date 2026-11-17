from __future__ import annotations

import streamlit as st

from config import settings
from core.db import get_engine, make_session_factory, upgrade_schema
from services import auth
from services.workflow import CareerPilot


@st.cache_resource(show_spinner=False)
def get_app() -> CareerPilot:
    upgrade_schema()          # idempotent: creates or upgrades tables (production also runs `alembic upgrade head` at start)
    return CareerPilot(make_session_factory(get_engine()))


def current_user():
    app = get_app()
    return auth.user_for_token(app.factory, st.session_state.get("token"))


def sign_out() -> None:
    auth.logout(get_app().factory, st.session_state.get("token"))
    for k in list(st.session_state.keys()):
        del st.session_state[k]

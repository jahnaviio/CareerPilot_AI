"""Deployment configuration, migrations, and a headless UI smoke test (Streamlit AppTest)."""
import dataclasses
import pathlib
import re

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

import config
from core.models import Base

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_database_url_normalisation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert config._database_url() == "postgresql+psycopg2://u:p@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert config._database_url().startswith("postgresql+psycopg2://")
    monkeypatch.setenv("DATABASE_URL", "")
    assert config._database_url().startswith("sqlite:///")


def test_migrations_upgrade_and_match_models_exactly(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    monkeypatch.setenv("DATABASE_URL", url)
    import importlib, config as c
    importlib.reload(c)                                   # alembic/env.py reads settings.database_url
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    assert {"users", "resume_profiles", "opportunities", "applications", "saved_opportunities", "notifications", "data_sources"} <= set(inspect(eng).get_table_names())
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations have drifted: {diff}"
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}
    importlib.reload(c)


def test_env_example_has_only_placeholders_and_gitignore_blocks_secrets():
    env = (ROOT / ".env.example").read_text()
    for line in env.splitlines():
        if re.match(r"^(LLM_API_KEY|DATABASE_URL)=", line):
            assert line.split("=", 1)[1].strip() in ("", ) or "your-" in line or "postgresql" in line, line
    assert not re.search(r"(sk-[A-Za-z0-9]{10,}|gsk_[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{12,})", env)
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()


def test_no_secrets_committed_anywhere():
    pat = re.compile(r"(sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA )?PRIVATE KEY-----|xox[bp]-[A-Za-z0-9-]{10,})")
    for f in ROOT.rglob("*"):
        if f.is_file() and f.suffix in {".py", ".md", ".yaml", ".yml", ".toml", ".txt", ".example", ".ini", ".sh"} and "node_modules" not in f.parts:
            assert not pat.search(f.read_text(errors="ignore")), f"possible secret in {f}"


def test_render_blueprint_and_requirements_present():
    r = (ROOT / "render.yaml").read_text()
    assert "alembic upgrade head" in r and "healthCheckPath" in r and "databases:" in r and "sync: false" in r      # secrets set in the dashboard
    req = (ROOT / "requirements.txt").read_text().lower()
    for pkg in ("streamlit", "sqlalchemy", "alembic", "pydantic", "argon2-cffi", "pymupdf", "python-docx", "psycopg2-binary", "chromadb", "scikit-learn"):
        assert pkg in req, pkg
    assert (ROOT / "Dockerfile").exists()


def test_production_hides_tracebacks_config():
    assert dataclasses.replace(config.settings, app_env="production").is_production


# ---------------------------- headless UI ----------------------------
@pytest.fixture()
def ui_user():
    from core.db import get_engine, init_db_for_dev, make_session_factory
    from services import auth
    eng = get_engine(); init_db_for_dev(eng)
    f = make_session_factory(eng)
    auth.register(f, "ui@x.co", "UI User", "Str0ng-Passw0rd")
    _, token, _ = auth.login(f, "ui@x.co", "Str0ng-Passw0rd")
    return token


def test_ui_signed_out_shows_auth_and_signed_in_shows_four_pages(ui_user):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception and "Understand your resume" in " ".join(m.value for m in at.markdown)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["token"] = ui_user
    at.run()
    assert not at.exception
    assert list(at.sidebar.radio[0].options) == ["Resume Intelligence", "Opportunities", "Saved Opportunities", "Application Tracker"]
    assert "Start with your resume" in " ".join(m.value for m in at.markdown)        # empty state, no data invented
    for page, needle in (("Opportunities", "Add your resume first"), ("Saved Opportunities", "Nothing saved yet"), ("Application Tracker", "No applications yet")):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        assert needle in " ".join(m.value for m in at.markdown), page

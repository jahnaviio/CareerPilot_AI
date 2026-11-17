"""SQLAlchemy engine/session management with transactional scope."""
from __future__ import annotations

import config  # noqa: F401  (sets SQLAlchemy env flags before it is imported)
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

_engine: Engine | None = None
_factory: sessionmaker | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine, _factory
    if url is not None:  # explicit engine (tests)
        eng = _make_engine(url)
        return eng
    if _engine is None:
        _engine = _make_engine(settings.database_url)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def _make_engine(url: str) -> Engine:
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # enforce foreign keys in SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return eng


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker | None = None) -> Iterator[Session]:
    """Commit on success, roll back on error, always close."""
    if factory is None:
        get_engine()
        factory = _factory
    assert factory is not None
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db_for_dev(engine: Engine | None = None) -> None:
    """Create tables directly. Production uses Alembic (`alembic upgrade head`)."""
    from core.models import Base
    Base.metadata.create_all(engine or get_engine())


def upgrade_schema(url: str | None = None) -> None:
    """Bring the configured database to the latest Alembic revision. Databases that an earlier version created with
    create_all (no alembic_version table) are adopted at the revision matching their columns, so no data is lost."""
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    base = Path(__file__).resolve().parent.parent
    cfg = Config(str(base / "alembic.ini"))
    cfg.set_main_option("script_location", str(base / "alembic"))
    if url:
        cfg.attributes["url"] = url
    eng = get_engine(url) if url else get_engine()
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    if "users" in tables and "alembic_version" not in tables:
        cols = {c["name"] for c in insp.get_columns("opportunities")}
        command.stamp(cfg, "0002" if "is_india" in cols else "0001")
    command.upgrade(cfg, "head")

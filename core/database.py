"""
Database layer for CareerPilot AI.

Single source of truth for the SQLite schema. All tables required by the
product spec live here: users, resumes, jobs, applications, saved_jobs,
notifications. Repositories (in repositories/) are the only code allowed
to issue SQL against these tables — nothing in services/, agents/, or ui/
should import sqlite3 directly.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import DB_PATH

SCHEMA_VERSION = 1

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL DEFAULT 'Student',
    email           TEXT UNIQUE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resumes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    raw_text        TEXT NOT NULL,
    extracted_skills TEXT,                 -- JSON-encoded list[str]
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,         -- 'remotive' | 'csv_seed' | 'manual'
    external_id     TEXT,                  -- id/url from the source, for de-duplication
    company         TEXT NOT NULL,
    role            TEXT NOT NULL,
    description     TEXT,
    required_skills TEXT,                  -- JSON-encoded list[str]
    location        TEXT,
    url             TEXT,
    posted_at       TEXT,
    discovered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id          INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    company         TEXT NOT NULL,
    role            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Applied'
                        CHECK (status IN ('Applied','Interview','Rejected','Offer')),
    applied_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS saved_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    match_score     INTEGER,
    saved_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, job_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,         -- 'new_job' | 'high_match' | 'status_change' | 'system'
    title           TEXT NOT NULL,
    body            TEXT,
    job_id          INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    is_read         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    resume_id       INTEGER REFERENCES resumes(id) ON DELETE SET NULL,
    match_score     INTEGER NOT NULL,
    matched_skills  TEXT,                  -- JSON-encoded list[str]
    computed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_discovered_at ON jobs(discovered_at);
CREATE INDEX IF NOT EXISTS idx_applications_user_status ON applications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_job_matches_user_score ON job_matches(user_id, match_score);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read);
"""


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a new SQLite connection with sane defaults (row factory, FKs on)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    """
    Context manager that commits on success, rolls back on exception, and
    always closes the connection. Use this everywhere instead of manually
    managing connect/commit/close.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Create all tables if they don't exist, and ensure a default user exists."""
    with db_session(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, name, email)
            VALUES (1, 'Student', 'student@careerpilot.local')
            """
        )

"""
Data access for the jobs table.

This is the piece that was missing entirely in the original codebase:
internships discovered by either the CSV seed or the live Remotive API
are persisted here instead of being thrown away after one Streamlit
render. Everything downstream (matching, notifications, stats) reads
from this table.
"""
from __future__ import annotations

import json
import sqlite3

from core.models import Job


def upsert_job(
    conn: sqlite3.Connection,
    source: str,
    company: str,
    role: str,
    description: str = "",
    required_skills: list[str] | None = None,
    location: str = "",
    url: str = "",
    posted_at: str = "",
    external_id: str = "",
) -> tuple[int, bool]:
    """
    Insert a job, or do nothing if (source, external_id) already exists.
    Returns (job_id, was_newly_inserted).
    """
    existing = conn.execute(
        "SELECT id FROM jobs WHERE source = ? AND external_id = ?",
        (source, external_id),
    ).fetchone()
    if existing:
        return existing["id"], False

    cursor = conn.execute(
        """
        INSERT INTO jobs
            (source, external_id, company, role, description,
             required_skills, location, url, posted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source,
            external_id,
            company,
            role,
            description,
            json.dumps(required_skills or []),
            location,
            url,
            posted_at,
        ),
    )
    return cursor.lastrowid, True


def list_jobs(
    conn: sqlite3.Connection,
    limit: int = 100,
    offset: int = 0,
    source: str | None = None,
) -> list[Job]:
    query = "SELECT * FROM jobs"
    params: list = []
    if source:
        query += " WHERE source = ?"
        params.append(source)
    query += " ORDER BY discovered_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = conn.execute(query, params).fetchall()
    return [Job.from_row(r) for r in rows]


def get_job(conn: sqlite3.Connection, job_id: int) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return Job.from_row(row) if row else None


def count_jobs(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]


def count_jobs_discovered_since(conn: sqlite3.Connection, since_iso: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS c FROM jobs WHERE discovered_at >= ?", (since_iso,)
    ).fetchone()["c"]


def list_jobs_discovered_since(conn: sqlite3.Connection, since_iso: str) -> list[Job]:
    rows = conn.execute(
        "SELECT * FROM jobs WHERE discovered_at >= ? ORDER BY discovered_at DESC",
        (since_iso,),
    ).fetchall()
    return [Job.from_row(r) for r in rows]


def search_jobs(conn: sqlite3.Connection, query_text: str, limit: int = 50) -> list[Job]:
    like = f"%{query_text}%"
    rows = conn.execute(
        """
        SELECT * FROM jobs
        WHERE company LIKE ? OR role LIKE ? OR description LIKE ?
        ORDER BY discovered_at DESC
        LIMIT ?
        """,
        (like, like, like, limit),
    ).fetchall()
    return [Job.from_row(r) for r in rows]

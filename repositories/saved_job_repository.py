"""Data access for the saved_jobs table (jobs a student bookmarks for later)."""
from __future__ import annotations

import sqlite3

from core.models import Job


def save_job(conn: sqlite3.Connection, user_id: int, job_id: int, match_score: int | None = None) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO saved_jobs (user_id, job_id, match_score)
        VALUES (?, ?, ?)
        """,
        (user_id, job_id, match_score),
    )


def unsave_job(conn: sqlite3.Connection, user_id: int, job_id: int) -> None:
    conn.execute(
        "DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    )


def is_saved(conn: sqlite3.Connection, user_id: int, job_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM saved_jobs WHERE user_id = ? AND job_id = ? LIMIT 1",
        (user_id, job_id),
    ).fetchone()
    return row is not None


def list_saved_jobs(conn: sqlite3.Connection, user_id: int) -> list[Job]:
    rows = conn.execute(
        """
        SELECT j.* FROM jobs j
        JOIN saved_jobs s ON s.job_id = j.id
        WHERE s.user_id = ?
        ORDER BY s.saved_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [Job.from_row(r) for r in rows]

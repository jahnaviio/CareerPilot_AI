"""Data access for the job_matches table (persisted resume-to-job match scores)."""
from __future__ import annotations

import json
import sqlite3

from core.models import JobMatch


def upsert_match(
    conn: sqlite3.Connection,
    user_id: int,
    job_id: int,
    match_score: int,
    matched_skills: list[str],
    resume_id: int | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO job_matches (user_id, job_id, resume_id, match_score, matched_skills, computed_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, job_id) DO UPDATE SET
            resume_id = excluded.resume_id,
            match_score = excluded.match_score,
            matched_skills = excluded.matched_skills,
            computed_at = datetime('now')
        """,
        (user_id, job_id, resume_id, match_score, json.dumps(matched_skills)),
    )


def get_match(conn: sqlite3.Connection, user_id: int, job_id: int) -> JobMatch | None:
    row = conn.execute(
        "SELECT * FROM job_matches WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    ).fetchone()
    return JobMatch.from_row(row) if row else None


def list_matches_for_user(
    conn: sqlite3.Connection, user_id: int, min_score: int = 0, limit: int = 100
) -> list[JobMatch]:
    rows = conn.execute(
        """
        SELECT * FROM job_matches
        WHERE user_id = ? AND match_score >= ?
        ORDER BY match_score DESC
        LIMIT ?
        """,
        (user_id, min_score, limit),
    ).fetchall()
    return [JobMatch.from_row(r) for r in rows]


def list_jobs_missing_match(conn: sqlite3.Connection, user_id: int, limit: int = 200) -> list[int]:
    """Job IDs that don't yet have a computed match score for this user."""
    rows = conn.execute(
        """
        SELECT j.id FROM jobs j
        LEFT JOIN job_matches m ON m.job_id = j.id AND m.user_id = ?
        WHERE m.id IS NULL
        ORDER BY j.discovered_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [r["id"] for r in rows]

"""Data access for the resumes table."""
from __future__ import annotations

import json
import sqlite3

from core.models import Resume


def create_resume(
    conn: sqlite3.Connection,
    user_id: int,
    filename: str,
    raw_text: str,
    extracted_skills: list[str],
    deactivate_others: bool = True,
) -> int:
    """
    Insert a new resume. By default marks all of the user's other resumes
    inactive so there's always exactly one "active" resume driving match
    scores — matches the common case of "I uploaded a new version".
    """
    if deactivate_others:
        conn.execute("UPDATE resumes SET is_active = 0 WHERE user_id = ?", (user_id,))

    cursor = conn.execute(
        """
        INSERT INTO resumes (user_id, filename, raw_text, extracted_skills, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (user_id, filename, raw_text, json.dumps(extracted_skills)),
    )
    return cursor.lastrowid


def get_active_resume(conn: sqlite3.Connection, user_id: int) -> Resume | None:
    row = conn.execute(
        """
        SELECT * FROM resumes
        WHERE user_id = ? AND is_active = 1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return Resume.from_row(row) if row else None


def list_resumes(conn: sqlite3.Connection, user_id: int) -> list[Resume]:
    rows = conn.execute(
        "SELECT * FROM resumes WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [Resume.from_row(r) for r in rows]


def get_resume(conn: sqlite3.Connection, resume_id: int) -> Resume | None:
    row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    return Resume.from_row(row) if row else None


def set_active_resume(conn: sqlite3.Connection, user_id: int, resume_id: int) -> None:
    conn.execute("UPDATE resumes SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.execute(
        "UPDATE resumes SET is_active = 1 WHERE id = ? AND user_id = ?",
        (resume_id, user_id),
    )

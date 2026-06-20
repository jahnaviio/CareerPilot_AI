"""Data access for the applications table (the Applied/Interview/Rejected/Offer pipeline)."""
from __future__ import annotations

import sqlite3

from core.models import Application

VALID_STATUSES = ("Applied", "Interview", "Rejected", "Offer")


def create_application(
    conn: sqlite3.Connection,
    user_id: int,
    company: str,
    role: str,
    job_id: int | None = None,
    status: str = "Applied",
    notes: str = "",
) -> int:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}.")

    cursor = conn.execute(
        """
        INSERT INTO applications (user_id, job_id, company, role, status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, job_id, company, role, status, notes),
    )
    return cursor.lastrowid


def list_applications(conn: sqlite3.Connection, user_id: int) -> list[Application]:
    rows = conn.execute(
        "SELECT * FROM applications WHERE user_id = ? ORDER BY applied_at DESC",
        (user_id,),
    ).fetchall()
    return [Application.from_row(r) for r in rows]


def update_status(conn: sqlite3.Connection, application_id: int, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}.")
    conn.execute(
        "UPDATE applications SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, application_id),
    )


def delete_application(conn: sqlite3.Connection, application_id: int) -> None:
    conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))


def count_by_status(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS c
        FROM applications
        WHERE user_id = ?
        GROUP BY status
        """,
        (user_id,),
    ).fetchall()
    counts = {status: 0 for status in VALID_STATUSES}
    for row in rows:
        counts[row["status"]] = row["c"]
    return counts


def has_applied(conn: sqlite3.Connection, user_id: int, job_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM applications WHERE user_id = ? AND job_id = ? LIMIT 1",
        (user_id, job_id),
    ).fetchone()
    return row is not None

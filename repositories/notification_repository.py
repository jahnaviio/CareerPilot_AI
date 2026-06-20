"""Data access for the notifications table."""
from __future__ import annotations

import sqlite3

from core.models import Notification


def create_notification(
    conn: sqlite3.Connection,
    user_id: int,
    type_: str,
    title: str,
    body: str = "",
    job_id: int | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO notifications (user_id, type, title, body, job_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, type_, title, body, job_id),
    )
    return cursor.lastrowid


def list_notifications(conn: sqlite3.Connection, user_id: int, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params: list = [user_id]
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [Notification.from_row(r) for r in rows]


def count_unread(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()["c"]


def mark_read(conn: sqlite3.Connection, notification_id: int) -> None:
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))


def mark_all_read(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))

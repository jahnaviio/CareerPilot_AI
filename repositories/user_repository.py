"""Data access for the users table."""
from __future__ import annotations

import sqlite3

from core.models import User


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return User(id=row["id"], name=row["name"], email=row["email"], created_at=row["created_at"])


def update_user_name(conn: sqlite3.Connection, user_id: int, name: str) -> None:
    conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

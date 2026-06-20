"""
One-time migration script: import applications from the OLD CareerPilot AI
database (a single `applications` table with columns id, company, role,
status) into the new schema's `applications` table.

Usage:
    python scripts/migrate_old_db.py /path/to/old_applications.db

Safe to run multiple times — it skips rows that look like exact duplicates
of something already imported (same company, role, and status).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import app_config  # noqa: E402
from core.database import db_session, init_db  # noqa: E402
from repositories import application_repository  # noqa: E402
from repositories.application_repository import VALID_STATUSES  # noqa: E402

_STATUS_MAP = {
    "applied": "Applied",
    "interview": "Interview",
    "interviewing": "Interview",
    "rejected": "Rejected",
    "offer": "Offer",
    "offered": "Offer",
}


def normalize_status(raw: str) -> str:
    return _STATUS_MAP.get((raw or "").strip().lower(), "Applied")


def migrate(old_db_path: str) -> None:
    init_db()

    old_conn = sqlite3.connect(old_db_path)
    old_conn.row_factory = sqlite3.Row
    rows = old_conn.execute("SELECT * FROM applications").fetchall()
    old_conn.close()

    if not rows:
        print("No rows found in the old database.")
        return

    with db_session() as conn:
        existing = application_repository.list_applications(conn, app_config.default_user_id)
        existing_keys = {(a.company.strip().lower(), a.role.strip().lower(), a.status) for a in existing}

        imported = 0
        skipped = 0
        for row in rows:
            company = (row["company"] or "Unknown Company").strip()
            role = (row["role"] or "Unknown Role").strip()
            status = normalize_status(row["status"] if "status" in row.keys() else "Applied")

            key = (company.lower(), role.lower(), status)
            if key in existing_keys:
                skipped += 1
                continue

            application_repository.create_application(
                conn, user_id=app_config.default_user_id, company=company, role=role, status=status
            )
            existing_keys.add(key)
            imported += 1

    print(f"Migration complete: {imported} application(s) imported, {skipped} duplicate(s) skipped.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/migrate_old_db.py /path/to/old_applications.db")
        sys.exit(1)

    target = sys.argv[1]
    if not Path(target).exists():
        print(f"File not found: {target}")
        sys.exit(1)

    migrate(target)

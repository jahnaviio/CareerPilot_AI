"""
Standalone job refresh script — runs ingestion, matching, and notification
generation without launching Streamlit. Intended to be run on a schedule
(cron, GitHub Actions, etc.) so jobs/notifications are fresh before
students open the app each day.

Usage:
    python scripts/refresh_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SEED_INTERNSHIPS_CSV, app_config  # noqa: E402
from core.database import db_session, init_db  # noqa: E402
from services.ingestion_service import run_full_ingestion  # noqa: E402
from services.matching_service import recompute_matches_for_user  # noqa: E402
from services.notification_service import generate_notifications_for_user  # noqa: E402


def main() -> None:
    init_db()

    with db_session() as conn:
        summary = run_full_ingestion(conn, str(SEED_INTERNSHIPS_CSV))
        print(f"Ingestion: {summary}")

        matched = recompute_matches_for_user(conn, app_config.default_user_id)
        print(f"Computed {matched} new match score(s).")

        notified = generate_notifications_for_user(conn, app_config.default_user_id)
        print(f"Created {notified} notification batch(es).")


if __name__ == "__main__":
    main()

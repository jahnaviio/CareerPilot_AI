"""Dashboard statistics aggregation."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from config import app_config
from repositories import (
    application_repository,
    job_match_repository,
    job_repository,
    notification_repository,
    resume_repository,
)


def get_dashboard_stats(conn: sqlite3.Connection, user_id: int) -> dict:
    """Single call that gathers everything the dashboard home page needs."""
    since_today = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    total_jobs = job_repository.count_jobs(conn)
    new_jobs_today = job_repository.count_jobs_discovered_since(conn, since_today)
    status_counts = application_repository.count_by_status(conn, user_id)
    total_applications = sum(status_counts.values())
    unread_notifications = notification_repository.count_unread(conn, user_id)
    active_resume = resume_repository.get_active_resume(conn, user_id)

    high_matches = job_match_repository.list_matches_for_user(
        conn, user_id, min_score=app_config.high_match_threshold, limit=1000
    )

    return {
        "total_jobs": total_jobs,
        "new_jobs_today": new_jobs_today,
        "total_applications": total_applications,
        "status_counts": status_counts,
        "unread_notifications": unread_notifications,
        "has_resume": active_resume is not None,
        "high_match_count": len(high_matches),
    }

"""
Notification Service.

Implements requirement #5: track newly discovered internships and surface
- New jobs today
- High match jobs
- Recommended opportunities

This runs after ingestion + matching (see scripts/refresh_data.py and the
"Refresh Jobs" action in the UI), turning raw DB state into actionable
notification rows.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from config import app_config
from repositories import job_match_repository, job_repository, notification_repository


def generate_notifications_for_user(conn: sqlite3.Connection, user_id: int) -> int:
    """
    Inspect recent jobs and match scores, create notification rows for
    anything noteworthy. Returns the number of notifications created.
    """
    created = 0
    created += _notify_new_jobs_today(conn, user_id)
    created += _notify_high_matches(conn, user_id)
    return created


def _notify_new_jobs_today(conn: sqlite3.Connection, user_id: int) -> int:
    since = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    new_jobs = job_repository.list_jobs_discovered_since(conn, since)

    if not new_jobs:
        return 0

    notification_repository.create_notification(
        conn,
        user_id=user_id,
        type_="new_job",
        title=f"{len(new_jobs)} new internship{'s' if len(new_jobs) != 1 else ''} found today",
        body=", ".join(f"{j.role} at {j.company}" for j in new_jobs[:5]),
    )
    return 1


def _notify_high_matches(conn: sqlite3.Connection, user_id: int) -> int:
    high_matches = job_match_repository.list_matches_for_user(
        conn, user_id, min_score=app_config.high_match_threshold, limit=10
    )
    created = 0
    for match in high_matches:
        job = job_repository.get_job(conn, match.job_id)
        if job is None:
            continue
        # One notification per high-match job — duplicate prevention happens
        # at the UI layer (the recent-notifications view is naturally capped),
        # acceptable for v1's polling-based refresh model.
        notification_repository.create_notification(
            conn,
            user_id=user_id,
            type_="high_match",
            title=f"Strong match: {job.role} at {job.company} ({match.match_score}%)",
            body=f"Your resume matches {match.match_score}% of the required skills for this role.",
            job_id=job.id,
        )
        created += 1
    return created


def get_recommended_jobs(conn: sqlite3.Connection, user_id: int, limit: int = 10):
    """Top-scoring jobs for the user, for the 'Recommended Opportunities' dashboard section."""
    matches = job_match_repository.list_matches_for_user(conn, user_id, min_score=0, limit=limit)
    recommendations = []
    for match in matches:
        job = job_repository.get_job(conn, match.job_id)
        if job:
            recommendations.append((job, match))
    return recommendations

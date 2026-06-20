"""
Smoke test suite for CareerPilot AI.

Replaces the original ad hoc `test_*.py` scripts (no framework, no
assertions — they only printed output for manual eyeballing). These are
real pytest tests with assertions, run against a temporary database so
they never touch your real data.

Run with:
    pytest tests/ -v
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import db_session, init_db  # noqa: E402
from repositories import (  # noqa: E402
    application_repository,
    job_match_repository,
    job_repository,
    notification_repository,
    resume_repository,
    saved_job_repository,
)
from agents.skill_matcher import calculate_match_score, extract_skills  # noqa: E402
from services.ingestion_service import ingest_csv_seed  # noqa: E402
from services.matching_service import recompute_matches_for_user  # noqa: E402

USER_ID = 1


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test_careerpilot.db"
    init_db(path)
    return path


def test_init_db_creates_all_required_tables(db_path):
    with db_session(db_path) as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    required = {"users", "resumes", "jobs", "applications", "saved_jobs", "notifications", "job_matches"}
    assert required.issubset(tables)


def test_extract_skills_finds_known_skills():
    text = "Experienced in Python, Machine Learning, and SQL."
    skills = extract_skills(text)
    assert "Python" in skills
    assert "Machine Learning" in skills
    assert "SQL" in skills
    assert "Java" not in skills


def test_calculate_match_score_full_overlap():
    result = calculate_match_score(["Python", "SQL"], ["Python", "SQL"])
    assert result["score"] == 100
    assert set(result["matched_skills"]) == {"Python", "SQL"}
    assert result["missing_skills"] == []


def test_calculate_match_score_partial_overlap():
    result = calculate_match_score(["Python"], ["Python", "SQL", "AWS"])
    assert 0 < result["score"] < 100
    assert "Python" in result["matched_skills"]
    assert "SQL" in result["missing_skills"]


def test_csv_seed_ingestion_is_idempotent(db_path, tmp_path):
    csv_path = tmp_path / "seed.csv"
    csv_path.write_text('Company,Role,Skills\nOpenAI,AI Intern,"Python,Machine Learning"\n')

    with db_session(db_path) as conn:
        first_run = ingest_csv_seed(conn, str(csv_path))
        second_run = ingest_csv_seed(conn, str(csv_path))

    assert first_run == 1
    assert second_run == 0  # no duplicates on re-run


def test_resume_create_and_get_active(db_path):
    with db_session(db_path) as conn:
        resume_repository.create_resume(conn, USER_ID, "r1.txt", "Python SQL", ["Python", "SQL"])
        resume_repository.create_resume(conn, USER_ID, "r2.txt", "Java", ["Java"])

    with db_session(db_path) as conn:
        active = resume_repository.get_active_resume(conn, USER_ID)

    # Second resume should be active; first should be auto-deactivated.
    assert active.filename == "r2.txt"
    assert active.is_active is True


def test_application_pipeline_status_transitions(db_path):
    with db_session(db_path) as conn:
        app_id = application_repository.create_application(
            conn, USER_ID, "Google", "ML Intern", status="Applied"
        )

    with db_session(db_path) as conn:
        application_repository.update_status(conn, app_id, "Interview")

    with db_session(db_path) as conn:
        apps = application_repository.list_applications(conn, USER_ID)

    assert len(apps) == 1
    assert apps[0].status == "Interview"


def test_application_rejects_invalid_status(db_path):
    with db_session(db_path) as conn:
        with pytest.raises(ValueError):
            application_repository.create_application(conn, USER_ID, "X", "Y", status="NotAStatus")


def test_matching_service_computes_scores_for_all_jobs(db_path, tmp_path):
    csv_path = tmp_path / "seed.csv"
    csv_path.write_text('Company,Role,Skills\nOpenAI,AI Intern,"Python,Machine Learning"\n')

    with db_session(db_path) as conn:
        ingest_csv_seed(conn, str(csv_path))
        resume_repository.create_resume(conn, USER_ID, "r.txt", "Python expert", ["Python"])
        computed = recompute_matches_for_user(conn, USER_ID, only_new_jobs=False)

    assert computed == 1

    with db_session(db_path) as conn:
        matches = job_match_repository.list_matches_for_user(conn, USER_ID)

    assert len(matches) == 1
    assert matches[0].match_score == 50  # 1 of 2 required skills matched


def test_saved_jobs_round_trip(db_path, tmp_path):
    csv_path = tmp_path / "seed.csv"
    csv_path.write_text('Company,Role,Skills\nOpenAI,AI Intern,"Python"\n')

    with db_session(db_path) as conn:
        ingest_csv_seed(conn, str(csv_path))
        job = job_repository.list_jobs(conn, limit=1)[0]
        saved_job_repository.save_job(conn, USER_ID, job.id)

    with db_session(db_path) as conn:
        assert saved_job_repository.is_saved(conn, USER_ID, job.id) is True
        saved = saved_job_repository.list_saved_jobs(conn, USER_ID)
        assert len(saved) == 1

        saved_job_repository.unsave_job(conn, USER_ID, job.id)
        assert saved_job_repository.is_saved(conn, USER_ID, job.id) is False


def test_notifications_unread_count(db_path):
    with db_session(db_path) as conn:
        notification_repository.create_notification(conn, USER_ID, "system", "Test notification")

    with db_session(db_path) as conn:
        assert notification_repository.count_unread(conn, USER_ID) == 1
        notifications = notification_repository.list_notifications(conn, USER_ID)
        notification_repository.mark_read(conn, notifications[0].id)

    with db_session(db_path) as conn:
        assert notification_repository.count_unread(conn, USER_ID) == 0

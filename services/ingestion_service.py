"""
Job Ingestion Service.

This is the architectural fix for "Real Internship Engine" (requirement
#4): the original code fetched jobs from a CSV or the Remotive API and
rendered them directly in Streamlit, discarding everything on the next
rerun. Here, every discovered job is upserted into the `jobs` table via
job_repository, de-duplicated by (source, external_id), so:

  - jobs accumulate over time instead of resetting each session
  - the same job is never inserted twice
  - downstream features (matching, notifications, stats) have something
    durable to read from
"""
from __future__ import annotations

import csv
import hashlib
import logging
import sqlite3

import requests

from agents.skill_matcher import extract_skills
from config import job_config
from repositories import job_repository

logger = logging.getLogger(__name__)


def _hash_id(*parts: str) -> str:
    """Stable external_id for sources (like the CSV seed) that have no native id."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def ingest_csv_seed(conn: sqlite3.Connection, csv_path: str) -> int:
    """
    Load the static seed CSV (Company, Role, Skills) into the jobs table.
    Safe to call repeatedly — duplicates are skipped via upsert_job.
    Returns the number of newly inserted jobs.
    """
    new_count = 0
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = (row.get("Company") or "").strip()
                role = (row.get("Role") or "").strip()
                skills_raw = (row.get("Skills") or "").strip()
                if not company or not role:
                    continue

                skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
                external_id = _hash_id(company, role)

                _, was_new = job_repository.upsert_job(
                    conn,
                    source="csv_seed",
                    external_id=external_id,
                    company=company,
                    role=role,
                    description="",
                    required_skills=skills,
                )
                if was_new:
                    new_count += 1
    except FileNotFoundError:
        logger.warning("Seed CSV not found at %s", csv_path)

    return new_count


def fetch_remotive_internships(conn: sqlite3.Connection) -> int:
    """
    Fetch live internship-relevant postings from the free Remotive API and
    persist new ones into the jobs table. Returns the number of newly
    inserted jobs. Network/API failures are caught and logged rather than
    raised, so a flaky external API never breaks the rest of the app.
    """
    try:
        response = requests.get(
            job_config.remotive_api_url, timeout=job_config.request_timeout_seconds
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
    except requests.RequestException as exc:
        logger.warning("Remotive API request failed: %s", exc)
        return 0
    except (ValueError, KeyError) as exc:
        logger.warning("Remotive API returned unexpected payload: %s", exc)
        return 0

    new_count = 0
    for job in jobs[: job_config.max_jobs_per_fetch]:
        title = job.get("title", "")
        title_lower = title.lower()

        if not any(keyword in title_lower for keyword in job_config.keywords):
            continue

        description = job.get("description", "") or ""
        skills = extract_skills(f"{title} {description}")

        _, was_new = job_repository.upsert_job(
            conn,
            source="remotive",
            external_id=str(job.get("id", "")),
            company=job.get("company_name", "Unknown Company"),
            role=title,
            description=description,
            required_skills=skills,
            location=job.get("candidate_required_location", ""),
            url=job.get("url", ""),
            posted_at=job.get("publication_date", ""),
        )
        if was_new:
            new_count += 1

    return new_count


def run_full_ingestion(conn: sqlite3.Connection, csv_path: str) -> dict:
    """Run both ingestion sources and return a summary of new jobs added."""
    new_from_csv = ingest_csv_seed(conn, csv_path)
    new_from_remotive = fetch_remotive_internships(conn)
    return {
        "new_from_csv": new_from_csv,
        "new_from_remotive": new_from_remotive,
        "total_new": new_from_csv + new_from_remotive,
    }

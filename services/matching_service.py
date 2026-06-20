"""
Matching Service.

Implements requirement #6 (Personalized Matching): automatically compare
stored jobs against the user's uploaded resume and persist match scores,
so the dashboard, job list, and notifications can all read precomputed
scores instead of recalculating on every page load.

Uses the deterministic skill-overlap scorer (agents/skill_matcher.py) for
bulk scoring — fast and free, runs against potentially hundreds of jobs.
The LLM-backed agents/resume_matcher.py is reserved for on-demand, single
job "deep analysis" (qualitative feedback), not bulk scoring.
"""
from __future__ import annotations

import sqlite3

from agents.skill_matcher import calculate_match_score
from repositories import job_match_repository, job_repository, resume_repository


def recompute_matches_for_user(conn: sqlite3.Connection, user_id: int, only_new_jobs: bool = True) -> int:
    """
    Compute (or refresh) match scores between the user's active resume and
    stored jobs. Returns the number of matches computed.

    only_new_jobs=True (default) only scores jobs that don't have a match
    record yet — cheap, safe to call on every page load. Pass False to
    force a full recompute (e.g. after the user uploads a new resume).
    """
    resume = resume_repository.get_active_resume(conn, user_id)
    if resume is None:
        return 0

    if only_new_jobs:
        job_ids = job_match_repository.list_jobs_missing_match(conn, user_id)
        jobs = [job_repository.get_job(conn, jid) for jid in job_ids]
        jobs = [j for j in jobs if j is not None]
    else:
        jobs = job_repository.list_jobs(conn, limit=1000)

    computed = 0
    for job in jobs:
        result = calculate_match_score(resume.extracted_skills, job.required_skills)
        job_match_repository.upsert_match(
            conn,
            user_id=user_id,
            job_id=job.id,
            match_score=result["score"],
            matched_skills=result["matched_skills"],
            resume_id=resume.id,
        )
        computed += 1

    return computed

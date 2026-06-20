"""
Domain models for CareerPilot AI.

These are lightweight dataclasses, not an ORM — repositories convert
sqlite3.Row objects into these so the rest of the app works with typed
objects instead of raw dict-like rows.

NOTE on multi-user: v1 ships in "single browser session = single student"
mode (DEFAULT_USER_ID from config). The schema is already fully
multi-user (every table is keyed by user_id with foreign keys), so adding
real authentication later is a UI-layer change, not a data-model change.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: int
    name: str
    email: Optional[str]
    created_at: str


@dataclass
class Resume:
    id: int
    user_id: int
    filename: str
    raw_text: str
    extracted_skills: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: str = ""

    @staticmethod
    def from_row(row) -> "Resume":
        return Resume(
            id=row["id"],
            user_id=row["user_id"],
            filename=row["filename"],
            raw_text=row["raw_text"],
            extracted_skills=json.loads(row["extracted_skills"] or "[]"),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )


@dataclass
class Job:
    id: int
    source: str
    company: str
    role: str
    description: str = ""
    required_skills: list[str] = field(default_factory=list)
    location: str = ""
    url: str = ""
    posted_at: str = ""
    discovered_at: str = ""
    external_id: str = ""

    @staticmethod
    def from_row(row) -> "Job":
        return Job(
            id=row["id"],
            source=row["source"],
            company=row["company"],
            role=row["role"],
            description=row["description"] or "",
            required_skills=json.loads(row["required_skills"] or "[]"),
            location=row["location"] or "",
            url=row["url"] or "",
            posted_at=row["posted_at"] or "",
            discovered_at=row["discovered_at"] or "",
            external_id=row["external_id"] or "",
        )


@dataclass
class Application:
    id: int
    user_id: int
    company: str
    role: str
    status: str
    applied_at: str
    updated_at: str
    job_id: Optional[int] = None
    notes: str = ""

    @staticmethod
    def from_row(row) -> "Application":
        return Application(
            id=row["id"],
            user_id=row["user_id"],
            job_id=row["job_id"],
            company=row["company"],
            role=row["role"],
            status=row["status"],
            applied_at=row["applied_at"],
            updated_at=row["updated_at"],
            notes=row["notes"] or "",
        )


@dataclass
class Notification:
    id: int
    user_id: int
    type: str
    title: str
    body: str
    is_read: bool
    created_at: str
    job_id: Optional[int] = None

    @staticmethod
    def from_row(row) -> "Notification":
        return Notification(
            id=row["id"],
            user_id=row["user_id"],
            type=row["type"],
            title=row["title"],
            body=row["body"] or "",
            job_id=row["job_id"],
            is_read=bool(row["is_read"]),
            created_at=row["created_at"],
        )


@dataclass
class JobMatch:
    id: int
    user_id: int
    job_id: int
    match_score: int
    matched_skills: list[str] = field(default_factory=list)
    resume_id: Optional[int] = None
    computed_at: str = ""

    @staticmethod
    def from_row(row) -> "JobMatch":
        return JobMatch(
            id=row["id"],
            user_id=row["user_id"],
            job_id=row["job_id"],
            resume_id=row["resume_id"],
            match_score=row["match_score"],
            matched_skills=json.loads(row["matched_skills"] or "[]"),
            computed_at=row["computed_at"],
        )

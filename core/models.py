"""ORM models. Every user-owned table carries user_id and is only reached through repositories
that always filter on it (see repositories/*)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, false)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Always timezone-aware UTC in Python, whatever the backend stores (SQLite drops tzinfo)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    ai_training_consent: Mapped[bool] = mapped_column(Boolean, default=False)  # never used for training unless True
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 of the token
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bucket: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class ResumeProfile(Base):
    """One uploaded resume + its validated structured profile."""
    __tablename__ = "resume_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 of file bytes -> skip reprocessing
    raw_text: Mapped[str] = mapped_column(Text)
    profile: Mapped[dict] = mapped_column(JSON)  # ResumeProfile pydantic dump (user-correctable)
    extraction_method: Mapped[str] = mapped_column(String(40), default="deterministic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    skills: Mapped[list["ExtractedSkill"]] = relationship(cascade="all, delete-orphan", back_populates="resume")
    __table_args__ = (UniqueConstraint("user_id", "content_hash", name="uq_resume_user_hash"),)


class ExtractedSkill(Base):
    __tablename__ = "extracted_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resume_profiles.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    strength: Mapped[str] = mapped_column(String(20))  # demonstrated | listed
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    resume: Mapped[ResumeProfile] = relationship(back_populates="skills")




class AIAnalysis(Base):
    """Cached AI/analysis outputs per resume (role recs, quality report, roadmap, explanations)."""
    __tablename__ = "ai_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resume_profiles.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # roles|quality|skill_gap|roadmap|readiness|explanation:<opp>|cover_letter:<opp>
    payload: Mapped[dict] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(40), default="deterministic")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    __table_args__ = (UniqueConstraint("resume_id", "kind", name="uq_analysis_resume_kind"),)


class DataSource(Base):
    """One configured employer board (e.g. greenhouse:anthropic) and its health."""
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(120), unique=True)  # "greenhouse:stripe"
    ats: Mapped[str] = mapped_column(String(20))
    board: Mapped[str] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(160))
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="never_run")  # ok|error|not_found|never_run
    last_error: Mapped[str] = mapped_column(Text, default="")
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(120), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    company: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(300), default="")
    work_mode: Mapped[str] = mapped_column(String(20), default="unknown")  # remote|hybrid|onsite|unknown
    employment_type: Mapped[str] = mapped_column(String(30), default="unknown")  # internship|full_time|part_time|contract|unknown
    is_internship: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    posting_url: Mapped[str] = mapped_column(String(1000))
    apply_url: Mapped[str] = mapped_column(String(1000))
    apply_url_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # host belongs to employer/ATS
    link_kind: Mapped[str] = mapped_column(String(20), default="official", server_default="official")  # official | aggregator (licensed API, not employer-direct)
    stipend_text: Mapped[str] = mapped_column(String(200), default="", server_default="")  # exactly what the posting says about pay
    is_paid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # None = posting does not say
    is_india: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), index=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    dedupe_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|unavailable|unverified
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_verified_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    __table_args__ = (UniqueConstraint("source_key", "external_id", name="uq_opp_source_ext"),
                      Index("ix_opp_status_internship", "status", "is_internship"))


class OpportunityMatch(Base):
    __tablename__ = "opportunity_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resume_profiles.id", ondelete="CASCADE"))
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict] = mapped_column(JSON)  # component scores, matched/missing skills, concerns
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "resume_id", "opportunity_id", name="uq_match"),)


class SavedOpportunity(Base):
    __tablename__ = "saved_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"))
    not_interested: Mapped[bool] = mapped_column(Boolean, default=False)
    saved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id", name="uq_saved"),)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True)
    company: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(300))
    listing_url: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="Interested")
    applied_on: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    interview_on: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    follow_up_on: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id", name="uq_app_user_opp"),)


class Notification(Base):
    """In-app reminders (e.g. follow-up due). Surfaced inside the Tracker, not as a separate page."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(500))
    ref_application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

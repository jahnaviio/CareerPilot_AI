from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.models import AuthSession, RateLimitEvent, User


def create(s: Session, email: str, name: str, password_hash: str) -> User:
    u = User(email=email.lower().strip(), name=name.strip()[:120], password_hash=password_hash)
    s.add(u)
    s.flush()
    return u


def by_email(s: Session, email: str) -> User | None:
    return s.scalar(select(User).where(User.email == email.lower().strip()))


def get(s: Session, user_id: int) -> User | None:
    return s.get(User, user_id)


def add_session(s: Session, user_id: int, token_hash: str, expires_at: datetime) -> None:
    s.add(AuthSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at))


def session_user(s: Session, token_hash: str, now: datetime) -> User | None:
    row = s.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash, AuthSession.expires_at > now))
    return s.get(User, row.user_id) if row else None


def drop_session(s: Session, token_hash: str) -> None:
    s.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))


def purge_user(s: Session, user_id: int) -> None:
    """Account deletion: FK cascades remove resumes, skills, matches, saved items, applications, analyses."""
    s.execute(delete(User).where(User.id == user_id))


def record_event(s: Session, user_id: int, bucket: str, now: datetime) -> None:
    s.add(RateLimitEvent(user_id=user_id, bucket=bucket, created_at=now))


def count_events(s: Session, user_id: int, bucket: str, since: datetime) -> int:
    from sqlalchemy import func
    return s.scalar(select(func.count()).select_from(RateLimitEvent).where(
        RateLimitEvent.user_id == user_id, RateLimitEvent.bucket == bucket, RateLimitEvent.created_at >= since)) or 0

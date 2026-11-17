from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from config import settings
from core.db import session_scope
from core.models import User
from core.security import (EMAIL_RE, hash_password, hash_token, new_session_token, validate_password_strength,
                           verify_password)
from repositories import users as repo

GENERIC_FAIL = "Invalid email or password."
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def register(factory: sessionmaker, email: str, name: str, password: str) -> tuple[User | None, str | None]:
    email = email.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return None, "Enter a valid email address."
    if (err := validate_password_strength(password)):
        return None, err
    with session_scope(factory) as s:
        if repo.by_email(s, email):
            return None, "An account with this email already exists."
        return repo.create(s, email, name or email.split("@")[0], hash_password(password)), None


def login(factory: sessionmaker, email: str, password: str, now: datetime | None = None) -> tuple[User | None, str | None, str | None]:
    """Returns (user, raw_session_token, error). Locks the account after repeated failures."""
    now = now or datetime.now(timezone.utc)
    with session_scope(factory) as s:
        u = repo.by_email(s, email)
        if u is None:
            verify_password(password, _DUMMY_HASH)  # equalise timing so unknown emails are not distinguishable
            return None, None, GENERIC_FAIL
        locked = u.locked_until
        if locked is not None and locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        if locked and locked > now:
            mins = int((locked - now).total_seconds() // 60) + 1
            return None, None, f"Too many attempts. Try again in about {mins} minute(s)."
        if not verify_password(password, u.password_hash):
            u.failed_logins += 1
            if u.failed_logins >= settings.login_max_attempts:
                u.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
                u.failed_logins = 0
            return None, None, GENERIC_FAIL
        u.failed_logins, u.locked_until = 0, None
        raw, h = new_session_token()
        repo.add_session(s, u.id, h, now + timedelta(hours=settings.session_ttl_hours))
        return u, raw, None


def user_for_token(factory: sessionmaker, raw: str | None, now: datetime | None = None) -> User | None:
    if not raw:
        return None
    with session_scope(factory) as s:
        return repo.session_user(s, hash_token(raw), now or datetime.now(timezone.utc))


def logout(factory: sessionmaker, raw: str | None) -> None:
    if raw:
        with session_scope(factory) as s:
            repo.drop_session(s, hash_token(raw))


def delete_account(factory: sessionmaker, user_id: int) -> None:
    with session_scope(factory) as s:
        repo.purge_user(s, user_id)


def allow_ai_call(factory: sessionmaker, user_id: int, bucket: str = "ai", now: datetime | None = None) -> tuple[bool, str]:
    """Per-user hourly quota for expensive AI endpoints."""
    now = now or datetime.now(timezone.utc)
    with session_scope(factory) as s:
        used = repo.count_events(s, user_id, bucket, now - timedelta(hours=1))
        if used >= settings.ai_calls_per_hour:
            return False, f"AI request limit reached ({settings.ai_calls_per_hour} per hour). Please try again later."
        repo.record_event(s, user_id, bucket, now)
    return True, ""

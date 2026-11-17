"""Every function takes user_id and filters on it: a user can never read or change another user's data."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from core.models import AIAnalysis, ExtractedSkill, OpportunityMatch, ResumeProfile
from nlp.schemas import ResumeProfile as ProfileSchema


def find_by_hash(s: Session, user_id: int, content_hash: str) -> ResumeProfile | None:
    return s.scalar(select(ResumeProfile).where(ResumeProfile.user_id == user_id, ResumeProfile.content_hash == content_hash))


def add(s: Session, user_id: int, filename: str, content_hash: str, raw_text: str, profile: ProfileSchema, method: str) -> ResumeProfile:
    s.execute(update(ResumeProfile).where(ResumeProfile.user_id == user_id).values(is_active=False))
    r = ResumeProfile(user_id=user_id, filename=filename, content_hash=content_hash, raw_text=raw_text,
                      profile=profile.model_dump(), extraction_method=method, is_active=True)
    s.add(r)
    s.flush()
    _sync_skills(s, r, profile)
    return r


def _sync_skills(s: Session, r: ResumeProfile, profile: ProfileSchema) -> None:
    s.execute(delete(ExtractedSkill).where(ExtractedSkill.resume_id == r.id))
    for sk in profile.skills:
        s.add(ExtractedSkill(resume_id=r.id, user_id=r.user_id, name=sk.name, category=sk.category, strength=sk.strength, evidence=sk.evidence))


def get_active(s: Session, user_id: int) -> ResumeProfile | None:
    return s.scalar(select(ResumeProfile).where(ResumeProfile.user_id == user_id, ResumeProfile.is_active.is_(True)).order_by(ResumeProfile.created_at.desc()))


def get(s: Session, user_id: int, resume_id: int) -> ResumeProfile | None:
    return s.scalar(select(ResumeProfile).where(ResumeProfile.id == resume_id, ResumeProfile.user_id == user_id))


def list_for_user(s: Session, user_id: int) -> list[ResumeProfile]:
    return list(s.scalars(select(ResumeProfile).where(ResumeProfile.user_id == user_id).order_by(ResumeProfile.created_at.desc())))


def activate(s: Session, user_id: int, resume_id: int) -> bool:
    if get(s, user_id, resume_id) is None:
        return False
    s.execute(update(ResumeProfile).where(ResumeProfile.user_id == user_id).values(is_active=False))
    s.execute(update(ResumeProfile).where(ResumeProfile.user_id == user_id, ResumeProfile.id == resume_id).values(is_active=True))
    return True


def save_corrected_profile(s: Session, user_id: int, resume_id: int, profile: ProfileSchema) -> bool:
    r = get(s, user_id, resume_id)
    if r is None:
        return False
    r.profile = profile.model_dump()
    r.user_edited = True
    _sync_skills(s, r, profile)
    s.execute(delete(AIAnalysis).where(AIAnalysis.resume_id == r.id, AIAnalysis.user_id == user_id))  # analyses are stale now
    s.execute(delete(OpportunityMatch).where(OpportunityMatch.resume_id == r.id, OpportunityMatch.user_id == user_id))
    return True


def delete_resume(s: Session, user_id: int, resume_id: int) -> bool:
    r = get(s, user_id, resume_id)
    if r is None:
        return False
    s.delete(r)
    return True


def purge_older_than(s: Session, cutoff: datetime) -> int:
    """Retention job: removes resumes (and cascades skills/matches/analyses) older than the cutoff."""
    rows = list(s.scalars(select(ResumeProfile).where(ResumeProfile.created_at < cutoff)))
    for r in rows:
        s.delete(r)
    return len(rows)


# ---- cached analyses ----
def get_analysis(s: Session, user_id: int, resume_id: int, kind: str) -> AIAnalysis | None:
    return s.scalar(select(AIAnalysis).where(AIAnalysis.user_id == user_id, AIAnalysis.resume_id == resume_id, AIAnalysis.kind == kind))


def set_analysis(s: Session, user_id: int, resume_id: int, kind: str, payload: dict, provider: str = "deterministic") -> None:
    row = get_analysis(s, user_id, resume_id, kind)
    if row:
        row.payload, row.provider = payload, provider
    else:
        s.add(AIAnalysis(user_id=user_id, resume_id=resume_id, kind=kind, payload=payload, provider=provider))

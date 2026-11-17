from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from core.models import DataSource, Opportunity, OpportunityMatch, SavedOpportunity, utcnow
from opportunities.normalize import NormalizedOpportunity, dedupe_key


def upsert_source(s: Session, entry: dict) -> DataSource:
    key = f"{entry['ats']}:{entry['board']}"
    row = s.scalar(select(DataSource).where(DataSource.source_key == key))
    if row is None:
        row = DataSource(source_key=key, ats=entry["ats"], board=entry["board"], company=entry["company"])
        s.add(row)
        s.flush()
    else:
        row.company = entry["company"]
    return row


def upsert_opportunity(s: Session, o: NormalizedOpportunity, apply_verified: bool, now: datetime) -> tuple[Opportunity, bool]:
    row = s.scalar(select(Opportunity).where(Opportunity.source_key == o.source_key, Opportunity.external_id == o.external_id))
    created = row is None
    if created:
        row = Opportunity(source_key=o.source_key, external_id=o.external_id, first_seen_at=now)
        s.add(row)
    row.company, row.title, row.description = o.company, o.title, o.description
    row.location, row.work_mode, row.employment_type = o.location, o.work_mode, o.employment_type
    row.is_internship = o.is_internship
    row.posting_url, row.apply_url, row.apply_url_verified = o.posting_url, o.apply_url, apply_verified
    row.link_kind, row.stipend_text, row.is_paid, row.is_india = o.link_kind, o.stipend_text, o.is_paid, o.is_india
    row.posted_at, row.deadline, row.required_skills = o.posted_at, o.deadline, o.required_skills
    row.dedupe_key = dedupe_key(o.company, o.title, o.location)
    row.status, row.last_seen_at, row.last_verified_at = "open", now, now
    s.flush()
    return row, created


def mark_unseen_unavailable(s: Session, source_key: str, seen_ids: set[str], now: datetime) -> int:
    """Only call after a SUCCESSFUL fetch of the source: listings it no longer returns are 'unavailable'."""
    rows = s.scalars(select(Opportunity).where(Opportunity.source_key == source_key, Opportunity.status == "open"))
    n = 0
    for r in rows:
        if r.external_id not in seen_ids:
            r.status = "unavailable"
            n += 1
    return n


def expire_past_deadlines(s: Session, now: datetime) -> int:
    res = s.execute(update(Opportunity).where(Opportunity.status == "open", Opportunity.deadline.is_not(None), Opportunity.deadline < now).values(status="unavailable"))
    return res.rowcount or 0


def mark_stale_unverified(s: Session, now: datetime, stale_hours: int) -> int:
    """Open listings whose source has not confirmed them recently are 'unverified' (never silently shown as fresh)."""
    cutoff = now - timedelta(hours=stale_hours)
    res = s.execute(update(Opportunity).where(Opportunity.status == "open", Opportunity.last_verified_at < cutoff).values(status="unverified"))
    return res.rowcount or 0


def get(s: Session, opp_id: int) -> Opportunity | None:
    return s.get(Opportunity, opp_id)


def _visible_clause():
    """Open listings that are either verified-official, or come from a licensed aggregator API (shown as such)."""
    return (Opportunity.status == "open") & (Opportunity.apply_url_verified.is_(True) | (Opportunity.link_kind == "aggregator"))


def list_visible(s: Session, *, internship: bool | None = None, company: str | None = None, location: str | None = None,
                 work_mode: str | None = None, posted_after: datetime | None = None, limit: int = 5000) -> list[Opportunity]:
    """Open listings only. Employer-official listings come first so cross-source duplicates collapse onto the official one."""
    q = select(Opportunity).where(_visible_clause())
    if internship is not None:
        q = q.where(Opportunity.is_internship.is_(internship))
    if company:
        q = q.where(Opportunity.company == company)
    if location:
        q = q.where(func.lower(Opportunity.location).contains(location.lower()))
    if work_mode:
        q = q.where(Opportunity.work_mode == work_mode)
    if posted_after:
        q = q.where(Opportunity.posted_at >= posted_after)
    rows = list(s.scalars(q.order_by(Opportunity.posted_at.desc().nullslast(), Opportunity.id).limit(limit)))
    rows.sort(key=lambda r: r.link_kind != "official")      # stable: keeps date order inside each group
    seen, out = set(), []
    for r in rows:
        if r.dedupe_key in seen:
            continue
        seen.add(r.dedupe_key)
        out.append(r)
    out.sort(key=lambda r: (r.posted_at is None, -(r.posted_at.timestamp() if r.posted_at else 0)))
    return out


def companies(s: Session) -> list[str]:
    return list(s.scalars(select(Opportunity.company).where(_visible_clause()).distinct().order_by(Opportunity.company)))


def freshness(s: Session) -> dict:
    last = s.scalar(select(func.max(DataSource.last_success_at)))
    total = s.scalar(select(func.count()).select_from(Opportunity).where(_visible_clause())) or 0
    srcs = list(s.scalars(select(DataSource)))
    return {"last_success_at": last, "open_listings": total, "sources_total": len(srcs),
            "sources_ok": sum(1 for x in srcs if x.last_status == "ok"),
            "sources_failing": [(x.source_key, x.last_status) for x in srcs if x.last_status in ("error", "not_found")]}


# ---- matches ----
def upsert_match(s: Session, user_id: int, resume_id: int, opp_id: int, score: float, detail: dict) -> None:
    row = s.scalar(select(OpportunityMatch).where(OpportunityMatch.user_id == user_id, OpportunityMatch.resume_id == resume_id, OpportunityMatch.opportunity_id == opp_id))
    if row:
        row.score, row.detail, row.computed_at = score, detail, utcnow()
    else:
        s.add(OpportunityMatch(user_id=user_id, resume_id=resume_id, opportunity_id=opp_id, score=score, detail=detail))


def matches_for(s: Session, user_id: int, resume_id: int) -> dict[int, OpportunityMatch]:
    rows = s.scalars(select(OpportunityMatch).where(OpportunityMatch.user_id == user_id, OpportunityMatch.resume_id == resume_id))
    return {m.opportunity_id: m for m in rows}


# ---- saved ----
def save(s: Session, user_id: int, opp_id: int) -> bool:
    """Returns True if newly saved. Duplicate saves are a no-op (also enforced by a unique constraint)."""
    row = s.scalar(select(SavedOpportunity).where(SavedOpportunity.user_id == user_id, SavedOpportunity.opportunity_id == opp_id))
    if row:
        if row.not_interested:
            row.not_interested = False
            return True
        return False
    s.add(SavedOpportunity(user_id=user_id, opportunity_id=opp_id))
    return True


def remove_saved(s: Session, user_id: int, opp_id: int) -> None:
    row = s.scalar(select(SavedOpportunity).where(SavedOpportunity.user_id == user_id, SavedOpportunity.opportunity_id == opp_id))
    if row:
        s.delete(row)


def set_not_interested(s: Session, user_id: int, opp_id: int, value: bool = True) -> None:
    row = s.scalar(select(SavedOpportunity).where(SavedOpportunity.user_id == user_id, SavedOpportunity.opportunity_id == opp_id))
    if row is None:
        row = SavedOpportunity(user_id=user_id, opportunity_id=opp_id)
        s.add(row)
    row.not_interested = value


def saved_ids(s: Session, user_id: int, include_not_interested: bool = False) -> set[int]:
    q = select(SavedOpportunity.opportunity_id).where(SavedOpportunity.user_id == user_id)
    if not include_not_interested:
        q = q.where(SavedOpportunity.not_interested.is_(False))
    return set(s.scalars(q))


def hidden_ids(s: Session, user_id: int) -> set[int]:
    return set(s.scalars(select(SavedOpportunity.opportunity_id).where(SavedOpportunity.user_id == user_id, SavedOpportunity.not_interested.is_(True))))


def list_saved(s: Session, user_id: int, internship: bool | None = None) -> list[tuple[Opportunity, SavedOpportunity]]:
    q = (select(Opportunity, SavedOpportunity).join(SavedOpportunity, SavedOpportunity.opportunity_id == Opportunity.id)
         .where(SavedOpportunity.user_id == user_id, SavedOpportunity.not_interested.is_(False)).order_by(SavedOpportunity.saved_at.desc()))
    if internship is not None:
        q = q.where(Opportunity.is_internship.is_(internship))
    return [(o, sv) for o, sv in s.execute(q).all()]

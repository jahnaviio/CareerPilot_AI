from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import Application, Notification, Opportunity, utcnow

STATUSES = ("Interested", "Applied", "Assessment", "Interview", "Offer", "Rejected")


def _check(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"Invalid status '{status}'")


def ensure_interested(s: Session, user_id: int, opp: Opportunity) -> tuple[Application, bool]:
    """Create an 'Interested' entry for a listing (no-op if one exists). Never marks Applied."""
    row = s.scalar(select(Application).where(Application.user_id == user_id, Application.opportunity_id == opp.id))
    if row:
        return row, False
    row = Application(user_id=user_id, opportunity_id=opp.id, company=opp.company, role=opp.title, listing_url=opp.posting_url, status="Interested")
    s.add(row)
    s.flush()
    return row, True


def create_manual(s: Session, user_id: int, company: str, role: str, status: str = "Interested", listing_url: str = "", notes: str = "") -> Application:
    _check(status)
    row = Application(user_id=user_id, company=company.strip()[:160], role=role.strip()[:300], listing_url=listing_url.strip()[:1000], status=status, notes=notes)
    if status == "Applied":
        row.applied_on = utcnow()
    s.add(row)
    s.flush()
    return row


def get(s: Session, user_id: int, app_id: int) -> Application | None:
    return s.scalar(select(Application).where(Application.id == app_id, Application.user_id == user_id))


def for_opportunity(s: Session, user_id: int, opp_id: int) -> Application | None:
    return s.scalar(select(Application).where(Application.user_id == user_id, Application.opportunity_id == opp_id))


def confirm_applied(s: Session, user_id: int, opp: Opportunity, when: datetime | None = None) -> Application:
    """Called ONLY after the user explicitly confirms they completed the application on the official site."""
    row, _ = ensure_interested(s, user_id, opp)
    row.status = "Applied"
    row.applied_on = when or utcnow()
    return row


def update(s: Session, user_id: int, app_id: int, **fields) -> bool:
    row = get(s, user_id, app_id)
    if row is None:
        return False
    if "status" in fields:
        _check(fields["status"])
        if fields["status"] == "Applied" and row.applied_on is None and "applied_on" not in fields:
            row.applied_on = utcnow()
    for k in ("status", "notes", "applied_on", "interview_on", "follow_up_on", "company", "role", "listing_url"):
        if k in fields:
            setattr(row, k, fields[k])
    return True


def delete(s: Session, user_id: int, app_id: int) -> bool:
    row = get(s, user_id, app_id)
    if row is None:
        return False
    s.delete(row)
    return True


def list_for_user(s: Session, user_id: int, statuses: list[str] | None = None) -> list[Application]:
    q = select(Application).where(Application.user_id == user_id).order_by(Application.updated_at.desc())
    if statuses:
        q = q.where(Application.status.in_(statuses))
    return list(s.scalars(q))


def counts(s: Session, user_id: int) -> dict[str, int]:
    c = {k: 0 for k in STATUSES}
    for a in list_for_user(s, user_id):
        c[a.status] += 1
    return c


def due_follow_ups(s: Session, user_id: int, now: datetime) -> list[Application]:
    return [a for a in list_for_user(s, user_id) if a.follow_up_on and a.follow_up_on <= now and a.status in ("Applied", "Assessment", "Interview")]


def sync_follow_up_notifications(s: Session, user_id: int, now: datetime) -> int:
    n = 0
    for a in due_follow_ups(s, user_id, now):
        exists = s.scalar(select(Notification).where(Notification.user_id == user_id, Notification.ref_application_id == a.id, Notification.kind == "follow_up", Notification.is_read.is_(False)))
        if not exists:
            s.add(Notification(user_id=user_id, kind="follow_up", message=f"Follow-up due for {a.role} at {a.company}", ref_application_id=a.id))
            n += 1
    return n


def unread_notifications(s: Session, user_id: int) -> list[Notification]:
    return list(s.scalars(select(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False)).order_by(Notification.created_at.desc())))


def mark_notification_read(s: Session, user_id: int, notification_id: int) -> bool:
    n = s.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))
    if n is None:
        return False
    n.is_read = True
    return True

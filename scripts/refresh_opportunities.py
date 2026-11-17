"""Fetch current postings from every board in the registry. Run from cron (see render.yaml) or by hand.
Also applies retention (removes resumes older than RESUME_RETENTION_DAYS)."""
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from core.db import get_engine, make_session_factory, session_scope, upgrade_schema  # noqa: E402
from repositories import resumes  # noqa: E402
from services.ingestion import load_registry, run_ingestion  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> int:
    upgrade_schema()
    engine = get_engine()
    factory = make_session_factory(engine)
    summary = run_ingestion(factory, load_registry())
    for r in summary.results:
        print(f"{r.source_key:45s} {r.status:10s} fetched={r.fetched:4d} new={r.new:4d} gone={r.unavailable:4d} unverified_urls={r.unverified_urls} {r.error}")
    print(f"\n{summary.ok}/{len(summary.results)} sources ok; {summary.expired} expired; {summary.stale} marked unverified (stale)")
    with session_scope(factory) as s:
        purged = resumes.purge_older_than(s, datetime.now(timezone.utc) - timedelta(days=settings.resume_retention_days))
    print(f"retention: removed {purged} resume(s) older than {settings.resume_retention_days} days")
    return 0 if summary.ok else 1       # non-zero when NO source worked, so cron shows the failure


if __name__ == "__main__":
    raise SystemExit(main())

"""Opportunity ingestion from public ATS board APIs. Real data only: if a source fails, nothing is invented
and previously stored listings are not re-labelled as freshly verified."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import sessionmaker

from config import settings
from core.db import session_scope
from core.models import DataSource
from core.security import verify_official_apply_url
from opportunities.http import FetchError, PoliteClient
from opportunities.sources.adapters import ADAPTERS, adzuna_url, parse_adzuna
from core.security import is_safe_external_url
from repositories import opportunities as repo

log = logging.getLogger(__name__)


@dataclass
class SourceResult:
    source_key: str
    status: str  # ok | error | not_found
    fetched: int = 0
    new: int = 0
    unavailable: int = 0
    unverified_urls: int = 0
    error: str = ""


@dataclass
class IngestSummary:
    results: list[SourceResult] = field(default_factory=list)
    expired: int = 0
    stale: int = 0

    @property
    def ok(self) -> int:
        return sum(1 for r in self.results if r.status == "ok")


def load_registry(path: str | Path | None = None) -> list[dict]:
    data = yaml.safe_load(Path(path or settings.source_registry_path).read_text()) or {}
    entries = data.get("sources", [])
    clean = []
    for e in entries:
        if e.get("ats") in ADAPTERS and e.get("board") and e.get("company"):
            clean.append(e)
        else:
            log.warning("Skipping invalid registry entry: %s", e)
    return clean


def ingest_source(factory: sessionmaker, entry: dict, client: PoliteClient, now: datetime | None = None) -> SourceResult:
    now = now or datetime.now(timezone.utc)
    key = f"{entry['ats']}:{entry['board']}"
    url_fn, parse_fn = ADAPTERS[entry["ats"]]
    res = SourceResult(key, "ok")
    try:
        data = client.get_json(url_fn(entry["board"], region=entry.get("region", "")))
        items = parse_fn(data, entry)
    except FetchError as exc:
        res.status, res.error = ("not_found" if exc.status == 404 else "error"), str(exc)
    except (ValueError, KeyError, TypeError) as exc:
        res.status, res.error = "error", f"Unexpected response format: {exc}"[:300]
    with session_scope(factory) as s:
        src = repo.upsert_source(s, entry)
        src.last_attempt_at = now
        if res.status != "ok":
            src.last_status, src.last_error = res.status, res.error
            log.warning("Source %s failed: %s", key, res.error)   # logs contain no resume data
            return res
        seen: set[str] = set()
        for o in items:
            ok = verify_official_apply_url(o.apply_url, entry.get("employer_domains", []), o.from_ats_api)
            if not ok:
                res.unverified_urls += 1
            _, created = repo.upsert_opportunity(s, o, ok, now)
            res.new += int(created)
            seen.add(o.external_id)
        res.fetched = len(items)
        res.unavailable = repo.mark_unseen_unavailable(s, key, seen, now)  # safe: this fetch succeeded
        src.last_success_at, src.last_status, src.last_error, src.jobs_seen = now, "ok", "", len(items)
    return res


ADZUNA_QUERIES = ["internship", "intern", "intern machine learning", "intern python", "intern data", "intern software", "intern artificial intelligence",
                  "intern web developer", "trainee software", "fresher software engineer", "graduate engineer trainee", "junior python developer"]


def adzuna_enabled() -> bool:
    return bool(settings.adzuna_app_id and settings.adzuna_app_key)


def ingest_adzuna(factory: sessionmaker, client: PoliteClient, now: datetime, pages: int = 3, queries: list[str] | None = None) -> SourceResult:
    """Licensed job-search API for India. Listings are labelled 'aggregator' and never presented as employer-official.
    Search results rotate, so absence is NOT treated as 'closed'; staleness handling (-> unverified) applies instead."""
    key = "adzuna:in"
    res = SourceResult(key, "ok")
    items, last_err = [], ""
    for q in (queries or ADZUNA_QUERIES):
        for page in range(1, pages + 1):
            try:
                data = client.get_json(adzuna_url(settings.adzuna_app_id, settings.adzuna_app_key, q, page))
                batch = parse_adzuna(data, "in")
            except FetchError as exc:
                last_err = str(exc)
                break
            except (ValueError, KeyError, TypeError) as exc:
                last_err = f"Unexpected response format: {exc}"[:200]
                break
            items.extend(batch)
            if len(batch) < 40:
                break
    with session_scope(factory) as s:
        src = repo.upsert_source(s, {"ats": "adzuna", "board": "in", "company": "Adzuna (India)"})
        src.last_attempt_at = now
        if not items:
            res.status, res.error = "error", last_err or "no results"
            src.last_status, src.last_error = res.status, res.error
            return res
        seen = set()
        for o in items:
            if o.external_id in seen or not is_safe_external_url(o.apply_url):
                continue
            seen.add(o.external_id)
            _, created = repo.upsert_opportunity(s, o, False, now)
            res.new += int(created)
        res.fetched = len(seen)
        src.last_success_at, src.last_status, src.last_error, src.jobs_seen = now, "ok", last_err[:200], len(seen)
    return res


def run_ingestion(factory: sessionmaker, entries: list[dict] | None = None, client: PoliteClient | None = None, now: datetime | None = None) -> IngestSummary:
    now = now or datetime.now(timezone.utc)
    entries = entries if entries is not None else load_registry()
    client = client or PoliteClient()
    summary = IngestSummary()
    for e in entries:
        summary.results.append(ingest_source(factory, e, client, now))
    if adzuna_enabled():
        summary.results.append(ingest_adzuna(factory, client, now))
    with session_scope(factory) as s:
        summary.expired = repo.expire_past_deadlines(s, now)
        summary.stale = repo.mark_stale_unverified(s, now, settings.stale_after_hours)
    return summary


def sources_health(factory: sessionmaker) -> list[DataSource]:
    from sqlalchemy import select
    with session_scope(factory) as s:
        return list(s.scalars(select(DataSource).order_by(DataSource.source_key)))

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from core.db import session_scope
from core.models import DataSource, Opportunity
from opportunities.http import FetchError
from opportunities.normalize import dedupe_key, detect_employment, extract_deadline, html_to_text
from opportunities.sources.adapters import parse_ashby, parse_greenhouse, parse_lever
from repositories import opportunities as repo
from services.ingestion import load_registry, run_ingestion
from tests.helpers import FakeClient, ashby_job, gh_job, ghost_greenhouse, lever_posting

GH = {"ats": "greenhouse", "board": "acmetest", "company": "Acme Test Co", "employer_domains": ["acmetest.example"]}
LV = {"ats": "lever", "board": "leverco", "company": "Lever Test Co", "employer_domains": ["leverco.example"]}
AS = {"ats": "ashby", "board": "ashbyco", "company": "Ashby Test Co", "employer_domains": ["ashbyco.example"]}
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def _visible(factory, **kw):
    with session_scope(factory) as s:
        return [(o.title, o.status) for o in repo.list_visible(s, **kw)]


def test_adapters_parse_documented_shapes():
    gh = parse_greenhouse(ghost_greenhouse([gh_job(1, "AI Engineering Intern", "&lt;p&gt;Python &amp;amp; RAG&lt;/p&gt;")]), GH)[0]
    assert gh.is_internship and gh.apply_url.startswith("https://job-boards.greenhouse.io/") and "Python" in gh.required_skills and "<p>" not in gh.description
    lv = parse_lever([lever_posting(1, "ML Intern")], LV)[0]
    assert lv.is_internship and lv.apply_url.endswith("/apply") and lv.work_mode == "remote" and lv.posted_at.year == 2025
    ab = parse_ashby({"jobs": [ashby_job(1, "Research Intern"), {**ashby_job(2, "Hidden"), "isListed": False}]}, AS)
    assert len(ab) == 1 and ab[0].employment_type == "internship" and ab[0].work_mode == "hybrid"


def test_adapters_reject_unexpected_payloads_and_skip_incomplete_rows():
    import pytest
    with pytest.raises(ValueError):
        parse_greenhouse({"oops": 1}, GH)
    with pytest.raises(ValueError):
        parse_lever({"not": "a list"}, LV)
    assert parse_greenhouse({"jobs": [{"id": 1, "title": "No url"}]}, GH) == []


def test_ingest_persists_real_fields_and_flags_official_urls(factory):
    client = FakeClient({"boards-api.greenhouse.io/v1/boards/acmetest": ghost_greenhouse([
        gh_job(1, "AI Intern", "Python PyTorch"), gh_job(2, "Backend Engineer", "Go and SQL"),
        gh_job(3, "Aggregated Intern", url_host="www.linkedin.com")])})
    summ = run_ingestion(factory, [GH], client, NOW)
    r = summ.results[0]
    assert r.status == "ok" and r.fetched == 3 and r.new == 3 and r.unverified_urls == 1
    vis = _visible(factory)
    assert ("Aggregated Intern", "open") not in vis                     # unverified host is never shown as official
    assert {t for t, _ in vis} == {"AI Intern", "Backend Engineer"}
    with session_scope(factory) as s:
        o = s.scalar(select(Opportunity).where(Opportunity.title == "AI Intern"))
        assert o.apply_url_verified and o.source_key == "greenhouse:acmetest" and o.last_verified_at == NOW and o.is_internship


def test_listing_that_disappears_becomes_unavailable_but_failed_fetch_changes_nothing(factory):
    run_ingestion(factory, [GH], FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern"), gh_job(2, "Data Intern")])}), NOW)
    run_ingestion(factory, [GH], FakeClient({"acmetest": FetchError("HTTP 503", 503)}), NOW + timedelta(hours=1))
    assert {t for t, _ in _visible(factory)} == {"AI Intern", "Data Intern"}     # outage must not wipe or fake anything
    with session_scope(factory) as s:
        src = s.scalar(select(DataSource))
        assert src.last_status == "error" and "503" in src.last_error and src.last_success_at == NOW
    run_ingestion(factory, [GH], FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern")])}), NOW + timedelta(hours=2))
    assert _visible(factory) == [("AI Intern", "open")]                          # Data Intern vanished -> hidden
    with session_scope(factory) as s:
        assert s.scalar(select(Opportunity.status).where(Opportunity.title == "Data Intern")) == "unavailable"


def test_unknown_board_is_reported_not_invented(factory):
    s = run_ingestion(factory, [GH], FakeClient({}), NOW)
    assert s.results[0].status == "not_found" and _visible(factory) == []


def test_stale_open_listings_become_unverified(factory):
    run_ingestion(factory, [GH], FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern")])}), NOW)
    with session_scope(factory) as s:
        assert repo.mark_stale_unverified(s, NOW + timedelta(hours=200), 72) == 1
    assert _visible(factory) == []


def test_deadline_expiry(factory):
    jd = "Apply by 2026-11-01. Python intern role."
    run_ingestion(factory, [GH], FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern", jd)])}), datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert _visible(factory) == [("AI Intern", "open")]
    with session_scope(factory) as s:
        assert repo.expire_past_deadlines(s, NOW) == 1
    assert _visible(factory) == []


def test_duplicate_listings_across_sources_are_collapsed(factory):
    a = ghost_greenhouse([gh_job(1, "ML Intern", loc="Remote")])
    b = [lever_posting(1, "ML Intern", loc="Remote")]
    run_ingestion(factory, [GH, LV], FakeClient({"acmetest": a, "leverco": b}), NOW)
    assert dedupe_key("Acme Test Co", "ML Intern", "Remote") != dedupe_key("Lever Test Co", "ML Intern", "Remote")
    with session_scope(factory) as s:
        s.add(Opportunity(source_key="lever:dup", external_id="x", company="Acme Test Co", title="ML Intern", description="", location="Remote", posting_url="https://jobs.lever.co/a",
                          apply_url="https://jobs.lever.co/a", apply_url_verified=True, dedupe_key=dedupe_key("Acme Test Co", "ML Intern", "Remote"), is_internship=True))
    titles = [t for t, _ in _visible(factory, internship=True)]
    assert titles.count("ML Intern") == 2     # one Acme (deduped from two rows) + one Lever; not 3


def test_reappearing_listing_reopens_and_upsert_is_idempotent(factory):
    c1 = FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern")])})
    run_ingestion(factory, [GH], c1, NOW)
    run_ingestion(factory, [GH], FakeClient({"acmetest": ghost_greenhouse([])}), NOW + timedelta(hours=1))
    assert _visible(factory) == []
    s2 = run_ingestion(factory, [GH], c1, NOW + timedelta(hours=2))
    assert _visible(factory) == [("AI Intern", "open")] and s2.results[0].new == 0
    with session_scope(factory) as s:
        assert len(list(s.scalars(select(Opportunity)))) == 1


def test_robots_blocked_source_is_not_fetched(factory):
    s = run_ingestion(factory, [GH], FakeClient({"acmetest": FetchError("Blocked by robots.txt", 403)}), NOW)
    assert s.results[0].status == "error" and "robots" in s.results[0].error


def test_normalisation_helpers():
    assert detect_employment("Software Engineering Intern") == "internship" and detect_employment("Staff Engineer") == "full_time"
    assert html_to_text("&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;").strip() == "• Python"
    assert extract_deadline("Application deadline: 15 December 2026").year == 2026 and extract_deadline("We hire year-round.") is None


def test_shipped_registry_is_valid_and_extensible():
    reg = load_registry()
    assert len(reg) >= 20 and all(e["ats"] in ("greenhouse", "lever", "ashby") for e in reg)
    assert len({(e["ats"], e["board"]) for e in reg}) == len(reg)
    assert all(e.get("employer_domains") for e in reg)


def test_no_seed_or_demo_data_ships_in_production_paths():
    import pathlib, re
    root = pathlib.Path(__file__).resolve().parent.parent
    assert not list(root.glob("data/*.csv")) and not list(root.rglob("seed_internships*"))
    banned = re.compile(r"seed_internships|fake_jobs|sample_jobs|demo_jobs|remotive", re.I)
    for f in list(root.glob("*.py")) + list(root.glob("services/*.py")) + list(root.glob("opportunities/**/*.py")) + list(root.glob("ui/**/*.py")) + list(root.glob("repositories/*.py")):
        assert not banned.search(f.read_text()), f

import dataclasses
import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

import services.ingestion as ing
from config import settings
from core.db import session_scope, upgrade_schema
from opportunities.directories import CAREER_PAGES, career_pages, platform_links
from opportunities.http import FetchError, redact
from opportunities.locations import CITIES, is_india, matches_city
from opportunities.sources.adapters import adzuna_url, parse_adzuna, parse_greenhouse, parse_lever
from opportunities.stipend import extract_stipend, money_range
from repositories import opportunities as repo
from services.ingestion import run_ingestion
from tests.helpers import FakeClient, gh_job, ghost_greenhouse, lever_posting

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
GH = {"ats": "greenhouse", "board": "acmetest", "company": "Acme Test Co", "employer_domains": []}


@pytest.mark.parametrize("txt,paid,has", [
    ("Stipend: ₹15,000 - ₹25,000 per month", True, "15,000"), ("Monthly stipend of Rs. 10000", True, "10000"), ("This is an unpaid internship", False, "Unpaid"),
    ("Paid internship with mentorship", True, "not stated"), ("We love Python", None, ""), ("Salary $30 - $45 per hour", True, "$30"),
    ("Stipend: not provided", False, "Unpaid"), ("Fees of 500 apply", None, "")])
def test_stipend_extraction_reports_only_what_is_stated(txt, paid, has):
    t, p = extract_stipend(txt)
    assert p is paid and has in t


def test_structured_pay_wins_and_formats_exactly():
    assert extract_stipend("nothing", "₹20,000 per month") == ("₹20,000 per month", True)
    assert money_range(15000, 25000, "INR", "month") == "₹15,000 – ₹25,000 per month" and money_range(None, None) == ""


@pytest.mark.parametrize("loc,ok", [("Bengaluru, Karnataka", True), ("Bangalore", True), ("Gurugram, Haryana", True), ("Remote - India", True), ("Hyderabad, Telangana, India", True),
                                    ("Indiana, USA", False), ("Remote - US", False), ("London, UK", False), ("Tokyo", False), ("", False)])
def test_india_detection(loc, ok):
    assert is_india(loc) is ok


def test_city_aliases():
    assert matches_city("Bangalore, KA", "Bengaluru") and matches_city("Noida", "Delhi NCR") and matches_city("Vizag", "Visakhapatnam") and not matches_city("Pune", "Mumbai")
    assert len(CITIES) >= 15


def test_ats_adapters_capture_stipend_and_india_flags():
    g = parse_greenhouse(ghost_greenhouse([gh_job(1, "ML Intern", "Stipend: ₹25,000 per month. Python.", loc="Bengaluru, India")]), GH)[0]
    assert g.is_india and g.is_paid is True and "25,000" in g.stipend_text
    lv = lever_posting(1, "Data Intern", loc="Hyderabad, India"); lv["salaryRange"] = {"min": 20000, "max": 30000, "currency": "INR", "interval": "per-month-salary"}
    o = parse_lever([lv], {"board": "leverco", "company": "L"})[0]
    assert o.is_india and o.is_paid is True and "20,000" in o.stipend_text


ADZ = {"count": 2, "results": [
    {"id": "1", "title": "Machine Learning Intern", "redirect_url": "https://www.adzuna.in/land/ad/1", "location": {"display_name": "Bengaluru, Karnataka"}, "company": {"display_name": "Startup A"},
     "description": "Stipend ₹20,000 per month. Python and PyTorch.", "created": "2026-11-10T00:00:00Z", "contract_time": "", "salary_min": 240000, "salary_max": 240000, "salary_is_predicted": "0"},
    {"id": "2", "title": "Python Intern", "redirect_url": "https://www.adzuna.in/land/ad/2", "location": {"display_name": "Pune"}, "company": {"display_name": "Startup B"},
     "description": "Work on Python.", "created": "2026-11-11T00:00:00Z", "salary_min": 100000, "salary_max": 500000, "salary_is_predicted": "1"}]}


def test_adzuna_parse_labels_aggregator_and_ignores_predicted_salary():
    a, b = parse_adzuna(ADZ)
    assert a.link_kind == "aggregator" and a.is_india and a.is_paid is True and a.is_internship
    assert b.is_paid is None and b.stipend_text == ""            # a predicted salary is not a stated stipend
    assert "app_key=KEY" in adzuna_url("ID", "KEY", "intern") and "country" not in adzuna_url("ID", "KEY", "intern")


def test_secrets_are_redacted_from_errors():
    assert "SECRET" not in redact("HTTPSConnectionPool url: /x?app_id=1&app_key=SECRET&what=a")


def test_adzuna_ingest_shows_aggregator_listings_labelled_and_official_wins_duplicates(factory, monkeypatch):
    monkeypatch.setattr(ing, "settings", dataclasses.replace(settings, adzuna_app_id="ID", adzuna_app_key="KEY"))
    client = FakeClient({"api.adzuna.com": ADZ, "acmetest": ghost_greenhouse([gh_job(7, "Machine Learning Intern", "Python", loc="Bengaluru, Karnataka")])})
    summ = run_ingestion(factory, [GH], client, NOW)
    assert [r.status for r in summ.results] == ["ok", "ok"] and summ.results[1].source_key == "adzuna:in"
    with session_scope(factory) as s:
        rows = repo.list_visible(s, internship=True)
    assert any(r.link_kind == "aggregator" and r.title == "Python Intern" for r in rows)
    assert all(not (r.link_kind == "aggregator" and r.apply_url_verified) for r in rows)      # never labelled official


def test_same_listing_from_employer_board_and_aggregator_shows_only_the_official_one(factory, monkeypatch):
    monkeypatch.setattr(ing, "settings", dataclasses.replace(settings, adzuna_app_id="ID", adzuna_app_key="KEY"))
    dup = {"results": [{**ADZ["results"][0], "id": "99", "title": "Machine Learning Intern", "company": {"display_name": "Acme Test Co"}, "location": {"display_name": "Bengaluru, India"}}]}
    client = FakeClient({"api.adzuna.com": dup, "acmetest": ghost_greenhouse([gh_job(7, "Machine Learning Intern", "Python", loc="Bengaluru, India")])})
    run_ingestion(factory, [GH], client, NOW)
    with session_scope(factory) as s:
        rows = [r for r in repo.list_visible(s) if r.title == "Machine Learning Intern"]
    assert len(rows) == 1 and rows[0].link_kind == "official" and rows[0].apply_url_verified


def test_adzuna_failure_does_not_break_other_sources(factory, monkeypatch):
    monkeypatch.setattr(ing, "settings", dataclasses.replace(settings, adzuna_app_id="ID", adzuna_app_key="KEY"))
    client = FakeClient({"api.adzuna.com": FetchError("HTTP 401", 401), "acmetest": ghost_greenhouse([gh_job(1, "AI Intern")])})
    summ = run_ingestion(factory, [GH], client, NOW)
    assert summ.results[0].status == "ok" and summ.results[1].status == "error" and "401" in summ.results[1].error


def test_adzuna_not_called_without_keys(factory):
    client = FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern")])})
    run_ingestion(factory, [GH], client, NOW)
    assert not any("adzuna" in u for u in client.requests)


def test_platform_links_and_careers_directory_are_safe_and_useful():
    from core.security import is_safe_external_url
    links = platform_links("machine learning", True)
    assert {"Internshala", "Unstop", "LinkedIn", "Naukri"} <= {l["name"] for l in links}
    assert all(is_safe_external_url(l["url"]) for l in links)
    assert "machine-learning" in links[0]["url"] and "work-from-home" in platform_links("python", True, True)[0]["url"]
    assert all(is_safe_external_url(u) for _, _, u in CAREER_PAGES) and len({u for _, _, u in CAREER_PAGES}) == len(CAREER_PAGES)
    assert [p["company"] for p in career_pages("flipkart")] == ["Flipkart"] and len(career_pages("fintech")) >= 3


def test_region_and_pay_filters():
    from types import SimpleNamespace as N
    from ui.pages.opportunities import PAY, WHERE, _pay_ok, _region_ok
    india_onsite = N(is_india=True, work_mode="onsite", is_paid=True)
    abroad_remote = N(is_india=False, work_mode="remote", is_paid=None)
    abroad_onsite = N(is_india=False, work_mode="onsite", is_paid=False)
    assert [_region_ok(o, WHERE[0]) for o in (india_onsite, abroad_remote, abroad_onsite)] == [True, True, False]   # India all + others remote only
    assert [_region_ok(o, WHERE[1]) for o in (india_onsite, abroad_remote, abroad_onsite)] == [True, False, False]
    assert [_region_ok(o, WHERE[2]) for o in (india_onsite, abroad_remote, abroad_onsite)] == [False, True, False]
    assert [_pay_ok(o, PAY[0]) for o in (india_onsite, abroad_remote, abroad_onsite)] == [True, False, False]
    assert [_pay_ok(o, PAY[1]) for o in (india_onsite, abroad_remote, abroad_onsite)] == [True, True, False]
    assert all(_pay_ok(o, PAY[2]) for o in (india_onsite, abroad_remote, abroad_onsite))


def test_existing_local_database_is_upgraded_without_losing_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    from alembic import command
    from alembic.config import Config
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini")); cfg.set_main_option("script_location", str(root / "alembic")); cfg.attributes["url"] = url
    command.upgrade(cfg, "0001")                                  # what the previous version of the app created
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("insert into opportunities (source_key, external_id, company, title, description, location, work_mode, employment_type, is_internship, posting_url, apply_url, apply_url_verified, required_skills, dedupe_key, status, first_seen_at, last_seen_at, last_verified_at) "
                       "values ('greenhouse:x','1','Old Co','Old Intern','d','Pune','unknown','internship',1,'https://a.io/1','https://a.io/1',1,'[]','k','open','2026-01-01','2026-01-01','2026-01-01')"))
        c.execute(text("drop table alembic_version"))             # simulate a DB made by create_all (no version table)
    upgrade_schema(url)
    with eng.connect() as c:
        row = c.execute(text("select title, link_kind, stipend_text, is_paid, is_india from opportunities")).one()
    assert tuple(row) == ("Old Intern", "official", "", None, 0)


def test_opportunities_page_lists_india_internships_by_default():
    from streamlit.testing.v1 import AppTest
    import pathlib
    from core.db import get_engine, init_db_for_dev, make_session_factory
    from services import auth
    from services.workflow import CareerPilot
    from tests.helpers import SAMPLE_RESUME, make_pdf
    root = pathlib.Path(__file__).resolve().parent.parent
    eng = get_engine(); init_db_for_dev(eng); f = make_session_factory(eng)
    auth.register(f, "india@x.co", "I", "Str0ng-Passw0rd")
    u, token, _ = auth.login(f, "india@x.co", "Str0ng-Passw0rd")
    board = [gh_job(i, f"Machine Learning Intern {i}", "Python PyTorch. Stipend: ₹20,000 per month.", loc="Bengaluru, India") for i in range(1, 31)]
    board += [gh_job(100, "Tokyo Research Intern", "Python.", loc="Tokyo, Japan"), gh_job(101, "Remote Data Intern", "Python SQL.", loc="Remote - US")]
    run_ingestion(f, [GH], FakeClient({"acmetest": ghost_greenhouse(board)}), NOW)
    CareerPilot(f, llm=None).analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME))
    at = AppTest.from_file(str(root / "app.py"), default_timeout=90)
    at.session_state["token"] = token
    at.run(); at.sidebar.radio[0].set_value("Opportunities").run()
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "Machine Learning Intern" in page and "Stipend: ₹20,000 per month" in page and "Tokyo Research Intern" not in page   # India shown first; abroad on-site hidden
    assert any("Show" in b.label and "more" in b.label for b in at.button)                                                        # list continues beyond the first 20


BANNED = ["backend", "deterministic", "embedding", "heuristic", "hashing", "AI status", "AI:", "retriev", "grounded", "extractive", "passage",
          "alembic", "DATABASE_URL", ".env", "ADZUNA_APP", "licensed", "LLM_", "token", "JSON", "R1", "J1"]


def _screen_text(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [b.label for b in at.button] + [e.label for e in at.expander]
    parts += [t.label for t in at.tabs] + [m.label for m in at.selectbox] + [s.label for s in at.sidebar.button]
    parts += [m.value for m in at.sidebar.markdown] + [c.value for c in at.sidebar.caption]
    return " ".join(str(p) for p in parts)


def test_no_technical_wording_on_any_page():
    from streamlit.testing.v1 import AppTest
    import pathlib
    from core.db import get_engine, init_db_for_dev, make_session_factory
    from services import auth
    from services.workflow import CareerPilot
    from tests.helpers import SAMPLE_RESUME, make_pdf
    root = pathlib.Path(__file__).resolve().parent.parent
    eng = get_engine(); init_db_for_dev(eng); f = make_session_factory(eng)
    auth.register(f, "plain@x.co", "P", "Str0ng-Passw0rd")
    u, token, _ = auth.login(f, "plain@x.co", "Str0ng-Passw0rd")
    run_ingestion(f, [GH], FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "Machine Learning Intern", "Python PyTorch. Stipend: ₹20,000 per month.", loc="Bengaluru, India")])}), NOW)
    CareerPilot(f, llm=None).analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME))
    at = AppTest.from_file(str(root / "app.py"), default_timeout=90)
    at.session_state["token"] = token
    at.run()
    sidebar = " ".join([m.value for m in at.sidebar.markdown] + [c.value for c in at.sidebar.caption])
    assert "LLM" not in sidebar and "AI:" not in sidebar and "No LLM" not in sidebar
    for page in ("Resume Intelligence", "Opportunities", "Saved Opportunities", "Application Tracker"):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
        text = _screen_text(at)
        from nlp.skills import TAXONOMY
        for skill in sorted(TAXONOMY, key=len, reverse=True):          # skill names are resume/job content, not app wording
            text = re.sub(re.escape(skill), " ", text, flags=re.I)
        for word in BANNED:
            assert word.lower() not in text.lower(), f"'{word}' shown on {page}"
        assert "Transformers" not in " ".join(m.value for m in at.sidebar.markdown)
    at.sidebar.radio[0].set_value("Resume Intelligence").run()
    stats = " ".join(m.value for m in at.markdown if "cp-stat" in m.value)
    assert "most important skills to add next" not in stats and "your strongest match" in stats

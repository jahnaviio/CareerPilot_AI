import json

import pytest
from sqlalchemy import select

from core.db import session_scope
from core.models import Notification, OpportunityMatch, SavedOpportunity
from repositories import applications as apps
from repositories import opportunities as orepo
from services import auth
from services.ingestion import run_ingestion
from services.workflow import FeatureUnavailable, QuotaExceeded
from tests.helpers import FakeClient, FakeLLM, SAMPLE_RESUME, ashby_job, gh_job, ghost_greenhouse, lever_posting, make_docx, make_pdf

ENTRIES = [{"ats": "greenhouse", "board": "acmetest", "company": "Acme Test Co", "employer_domains": []},
           {"ats": "lever", "board": "leverco", "company": "Lever Test Co", "employer_domains": []},
           {"ats": "ashby", "board": "ashbyco", "company": "Ashby Test Co", "employer_domains": []}]
ROUTES = {"acmetest": ghost_greenhouse([gh_job(1, "Machine Learning Intern", "Python, PyTorch, RAG and Docker. Currently pursuing a degree."),
                                         gh_job(2, "Senior Staff Sales Manager", "10+ years of experience in enterprise sales and Excel.")]),
          "leverco": [lever_posting(1, "Software Engineering Intern")],
          "ashbyco": {"jobs": [ashby_job(1, "LLM Research Intern")]}}


@pytest.fixture()
def world(app, factory):
    run_ingestion(factory, ENTRIES, FakeClient(ROUTES))
    u, _ = auth.register(factory, "w@x.co", "W", "Str0ng-Passw0rd")
    return app, factory, u


def test_upload_pdf_and_docx_then_dedupe_same_file(app, factory):
    u, _ = auth.register(factory, "u@x.co", "U", "Str0ng-Passw0rd")
    pdf = make_pdf(SAMPLE_RESUME)            # same bytes uploaded twice (ReportLab stamps a time, so build once)
    r1 = app.analyse_resume(u.id, "cv.pdf", pdf)
    assert r1.resume_id and not r1.reused and not r1.error
    r2 = app.analyse_resume(u.id, "cv-copy.pdf", pdf)
    assert r2.reused and r2.resume_id == r1.resume_id                       # identical bytes: not re-processed
    r3 = app.analyse_resume(u.id, "cv.docx", make_docx(SAMPLE_RESUME))
    assert r3.resume_id != r1.resume_id and app.load(u.id)[0].id == r3.resume_id   # replacing makes the new one active


def test_upload_errors_are_user_friendly(app, factory):
    u, _ = auth.register(factory, "e@x.co", "U", "Str0ng-Passw0rd")
    for name, data in (("a.txt", b"hello"), ("a.pdf", b"nope"), ("a.pdf", b"%PDF-1.4 broken")):
        res = app.analyse_resume(u.id, name, data)
        assert res.error and res.resume_id is None
    assert app.load(u.id) == (None, None)


def test_full_pipeline_roles_quality_gap_roadmap_readiness(world):
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    roles = app.roles(u.id, rid)
    assert len(roles) == 12 and roles == sorted(roles, key=lambda r: -r.score)
    assert app.roles(u.id, rid)[0].score == roles[0].score                  # served from cache, stable
    assert app.quality(u.id, rid)["issues"] is not None
    gap = app.skill_gap(u.id, rid, "genai_engineer")
    assert any(g["skill"] == "LLMs" for g in gap["gaps"]) and all(g["skill"] not in {e["skill"] for e in gap["existing"]} for g in gap["gaps"])
    for days in (30, 60, 90):
        rm = app.roadmap(u.id, rid, "genai_engineer", days)
        assert len(rm["weeks"]) == {30: 4, 60: 8, 90: 12}[days]
        scheduled = [w["skill"] for w in rm["weeks"] if w["skill"]]
        demonstrated = {e["skill"] for e in gap["existing"]}
        assert not demonstrated & set(scheduled)                              # never schedules what you already demonstrate
    app.set_roadmap_task(u.id, rid, "genai_engineer", 30, "w1:topics", True)
    assert app.roadmap_progress(u.id, rid, "genai_engineer", 30) == {"w1:topics": True}
    assert "disclaimer" in app.readiness(u.id, rid)


def test_match_all_ranks_relevant_first_and_hides_unverified(world):
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    m = app.match_all(u.id, rid, internship=True)
    with session_scope(factory) as s:
        titles = {o.id: o.title for o in orepo.list_visible(s, internship=True)}
    ranked = sorted(m, key=lambda i: -m[i]["score"])
    assert set(m) == set(titles) and titles[ranked[0]] in ("Machine Learning Intern", "LLM Research Intern")
    allm = app.match_all(u.id, rid)
    sales = next(i for i, t in {o.id: o.title for o in _all(factory)}.items() if "Sales" in t)
    assert allm[sales]["score"] <= 35 and any("senior" in c.lower() for c in allm[sales]["concerns"])
    assert app.match_all(u.id, rid) == allm                                   # persisted, stable


def _all(factory):
    with session_scope(factory) as s:
        return orepo.list_visible(s)


def test_editing_profile_invalidates_cached_analysis_and_matches(world):
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    app.roles(u.id, rid); app.match_all(u.id, rid)
    r, p = app.load(u.id, rid)
    from nlp.schemas import Skill
    p.skills.append(Skill(name="Kubernetes", category="tool", strength="listed", user_added=True))
    assert app.update_profile(u.id, rid, p)
    with session_scope(factory) as s:
        assert s.scalar(select(OpportunityMatch)) is None
    assert "kubernetes" in app.load(u.id, rid)[1].skill_map() and app.load(u.id, rid)[0].user_edited


def test_explanation_extractive_without_llm_then_cached(world):
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    m = app.match_all(u.id, rid, internship=True)
    oid = max(m, key=lambda i: m[i]["score"])
    out = app.explain_match(u.id, rid, oid)
    assert out["mode"] == "extractive" and out["passages"] and any(k.startswith("R") for k in out["passages"]) and any(k.startswith("J") for k in out["passages"])
    assert app.explain_match(u.id, rid, oid) == out


def test_rag_explanation_drops_uncited_and_invented_citations(world):
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id      # deterministic upload (no LLM yet)
    app.llm = FakeLLM([json.dumps({"summary": "Good fit.", "strengths": [
        {"text": "Built a RAG assistant", "cites": ["R1"]}, {"text": "Led a team of 50", "cites": []}, {"text": "Fake claim", "cites": ["R99"]}],
        "gaps": [{"text": "No Kubernetes", "cites": ["J1"]}], "next_steps": ["Learn K8s"]})])
    m = app.match_all(u.id, rid, internship=True)
    out = app.explain_match(u.id, rid, max(m, key=lambda i: m[i]["score"]))
    assert out["mode"] == "llm_grounded" and out["dropped_ungrounded_claims"] == 2
    assert [c["text"] for c in out["strengths"]] == ["Built a RAG assistant"] and out["gaps"][0]["cites"] == ["J1"]


def test_tailor_and_cover_letter_require_llm_and_flag_invented_skills(world):
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    m = app.match_all(u.id, rid, internship=True)
    oid = max(m, key=lambda i: m[i]["score"])
    with pytest.raises(FeatureUnavailable):
        app.tailor_resume(u.id, rid, oid)                                    # no LLM configured -> clear error, no fake text
    app.llm = FakeLLM(["Priya Test\nSkills: Python, PyTorch, Kubernetes, Terraform"])
    out = app.tailor_resume(u.id, rid, oid)
    assert set(out["unsupported_skills"]) == {"Kubernetes"} and "Kubernetes" in out["warning"]
    app.llm = FakeLLM(["Dear team, I built RAG systems with Python and AWS."])
    assert app.cover_letter(u.id, rid, oid)["unsupported_skills"] == ["AWS"]


def test_llm_quota_enforced(world, monkeypatch):
    app, factory, u = world
    import dataclasses, services.auth as a
    from config import settings
    monkeypatch.setattr(a, "settings", dataclasses.replace(settings, ai_calls_per_hour=1))
    app.llm = FakeLLM(["x", "y"])
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id      # consumes the 1 call (profile enrichment)
    with pytest.raises(QuotaExceeded):
        app.cover_letter(u.id, rid, _all(factory)[0].id)


# ------------------------- tracker / saved -------------------------
def test_saved_opportunities_no_duplicates_remove_and_not_interested(world):
    app, factory, u = world
    opp = _all(factory)[0]
    with session_scope(factory) as s:
        assert orepo.save(s, u.id, opp.id) is True and orepo.save(s, u.id, opp.id) is False
    with session_scope(factory) as s:
        assert len(list(s.scalars(select(SavedOpportunity)))) == 1 and len(orepo.list_saved(s, u.id)) == 1
        assert len(orepo.list_saved(s, u.id, internship=not opp.is_internship)) == 0
        orepo.set_not_interested(s, u.id, opp.id)
    with session_scope(factory) as s:
        assert orepo.list_saved(s, u.id) == [] and opp.id in orepo.hidden_ids(s, u.id)
        orepo.remove_saved(s, u.id, opp.id)
        assert opp.id not in orepo.saved_ids(s, u.id, True)


def test_apply_click_does_not_mark_applied_until_confirmed(world):
    app, factory, u = world
    opp = _all(factory)[0]
    with session_scope(factory) as s:
        row, created = apps.ensure_interested(s, u.id, opp)
        assert created and row.status == "Interested" and row.applied_on is None
        assert apps.ensure_interested(s, u.id, opp)[1] is False             # idempotent
    with session_scope(factory) as s:
        assert apps.counts(s, u.id)["Applied"] == 0
        a = apps.confirm_applied(s, u.id, opp)                              # explicit user confirmation
        assert a.status == "Applied" and a.applied_on is not None and a.listing_url == opp.posting_url


def test_tracker_statuses_dates_notes_filters_and_validation(world):
    from datetime import datetime, timedelta, timezone
    app, factory, u = world
    now = datetime.now(timezone.utc)
    with session_scope(factory) as s:
        a = apps.create_manual(s, u.id, "Acme", "ML Intern", "Interested", notes="n")
        b = apps.create_manual(s, u.id, "Beta", "Data Intern", "Applied")
        assert b.applied_on is not None
        with pytest.raises(ValueError):
            apps.create_manual(s, u.id, "X", "Y", "Hired!!")
        assert apps.update(s, u.id, a.id, status="Interview", interview_on=now + timedelta(days=3), follow_up_on=now - timedelta(days=1), notes="prep") is True
        with pytest.raises(ValueError):
            apps.update(s, u.id, a.id, status="Nope")
        aid = a.id
    with session_scope(factory) as s:
        got = apps.get(s, u.id, aid)
        assert got.status == "Interview" and got.notes == "prep" and got.interview_on > now
        assert [x.company for x in apps.list_for_user(s, u.id, ["Applied"])] == ["Beta"]
        c = apps.counts(s, u.id)
        assert c["Interview"] == 1 and c["Applied"] == 1 and set(c) == set(apps.STATUSES)
        assert [x.id for x in apps.due_follow_ups(s, u.id, now)] == [aid]
        assert apps.sync_follow_up_notifications(s, u.id, now) == 1 and apps.sync_follow_up_notifications(s, u.id, now) == 0
        assert apps.delete(s, u.id, aid) is True
    with session_scope(factory) as s:
        assert s.scalar(select(Notification)) is None                        # cascaded with the application


def test_notifications_unread_dismiss_and_isolation(world):
    from datetime import datetime, timedelta, timezone
    app, factory, u = world
    other, _ = auth.register(factory, "other@x.co", "O", "Str0ng-Passw0rd")
    now = datetime.now(timezone.utc)
    with session_scope(factory) as s:
        a = apps.create_manual(s, u.id, "Acme", "Intern", "Applied")
        apps.update(s, u.id, a.id, follow_up_on=now - timedelta(days=1))
        apps.sync_follow_up_notifications(s, u.id, now)
    with session_scope(factory) as s:
        [n] = apps.unread_notifications(s, u.id)
        assert "Acme" in n.message and apps.unread_notifications(s, other.id) == []
        assert apps.mark_notification_read(s, other.id, n.id) is False            # cannot dismiss someone else's
        assert apps.mark_notification_read(s, u.id, n.id) is True
    with session_scope(factory) as s:
        assert apps.unread_notifications(s, u.id) == []


def test_explanation_survives_a_restart_of_a_non_persistent_vector_store(world, embedder):
    from rag.store import VectorStore
    app, factory, u = world
    rid = app.analyse_resume(u.id, "cv.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    m = app.match_all(u.id, rid, internship=True)
    app.store = VectorStore(embedder, force_memory=True)                      # simulates a process restart: all vectors gone
    out = app.explain_match(u.id, rid, max(m, key=lambda i: m[i]["score"]))
    assert any(k.startswith("R") for k in out["passages"]) and any(k.startswith("J") for k in out["passages"])

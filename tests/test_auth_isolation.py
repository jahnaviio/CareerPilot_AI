from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config import settings
from core.db import session_scope
from core.models import AuthSession, ExtractedSkill, ResumeProfile, User
from nlp.profile_builder import build_profile
from repositories import applications as apps
from repositories import opportunities as orepo
from repositories import resumes as rrepo
from services import auth
from tests.helpers import SAMPLE_RESUME, make_pdf

PW = "Str0ng-Passw0rd"


def _user(factory, email, name="U"):
    u, err = auth.register(factory, email, name, PW)
    assert err is None
    return u


def test_register_validation_and_duplicates(factory):
    assert auth.register(factory, "not-an-email", "x", PW)[1]
    assert auth.register(factory, "a@b.co", "x", "short")[1]
    assert auth.register(factory, "a@b.co", "x", PW)[1] is None
    assert "already exists" in auth.register(factory, "A@B.co", "x", PW)[1]          # case-insensitive


def test_password_is_stored_hashed(factory):
    _user(factory, "h@x.co")
    with session_scope(factory) as s:
        assert s.scalar(select(User.password_hash)).startswith("$argon2") and PW not in s.scalar(select(User.password_hash))


def test_login_success_session_roundtrip_logout_and_expiry(factory):
    _user(factory, "l@x.co")
    u, tok, err = auth.login(factory, "l@x.co", PW)
    assert err is None and auth.user_for_token(factory, tok).id == u.id
    with session_scope(factory) as s:
        assert tok not in [r.token_hash for r in s.scalars(select(AuthSession))]       # raw token never stored
    assert auth.user_for_token(factory, tok, now=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours + 1)) is None
    assert auth.user_for_token(factory, "forged") is None and auth.user_for_token(factory, None) is None
    auth.logout(factory, tok)
    assert auth.user_for_token(factory, tok) is None


def test_failed_logins_lock_account_and_errors_do_not_leak_which_part_was_wrong(factory):
    _user(factory, "k@x.co")
    e_unknown = auth.login(factory, "nobody@x.co", PW)[2]
    for _ in range(settings.login_max_attempts):
        e_wrong = auth.login(factory, "k@x.co", "bad-password")[2]
    assert e_wrong == e_unknown == auth.GENERIC_FAIL
    assert "Too many attempts" in auth.login(factory, "k@x.co", PW)[2]                # even the right password is refused while locked
    later = datetime.now(timezone.utc) + timedelta(minutes=settings.login_lockout_minutes + 1)
    assert auth.login(factory, "k@x.co", PW, now=later)[2] is None


def test_ai_rate_limit(factory, monkeypatch):
    u = _user(factory, "r@x.co")
    import dataclasses, services.auth as a
    monkeypatch.setattr(a, "settings", dataclasses.replace(settings, ai_calls_per_hour=2))
    assert auth.allow_ai_call(factory, u.id)[0] and auth.allow_ai_call(factory, u.id)[0]
    ok, msg = auth.allow_ai_call(factory, u.id)
    assert not ok and "limit" in msg.lower()
    other = _user(factory, "r2@x.co")
    assert auth.allow_ai_call(factory, other.id)[0]                                    # quotas are per user


def test_resume_data_is_isolated_between_users(factory):
    a, b = _user(factory, "a@x.co"), _user(factory, "b@x.co")
    p, *_ = build_profile(SAMPLE_RESUME)
    with session_scope(factory) as s:
        r = rrepo.add(s, a.id, "a.pdf", "h1", SAMPLE_RESUME, p, "deterministic")
        rrepo.set_analysis(s, a.id, r.id, "roles", {"secret": 1})
        rid = r.id
    with session_scope(factory) as s:
        assert rrepo.get(s, b.id, rid) is None and rrepo.get_active(s, b.id) is None and rrepo.list_for_user(s, b.id) == []
        assert rrepo.get_analysis(s, b.id, rid, "roles") is None
        assert rrepo.delete_resume(s, b.id, rid) is False and rrepo.activate(s, b.id, rid) is False
        assert rrepo.save_corrected_profile(s, b.id, rid, p) is False
    with session_scope(factory) as s:
        assert rrepo.get(s, a.id, rid) is not None                                      # still intact for the owner


def test_applications_and_saved_items_are_isolated(factory, app):
    from tests.helpers import FakeClient, gh_job, ghost_greenhouse
    from services.ingestion import run_ingestion
    run_ingestion(factory, [{"ats": "greenhouse", "board": "acmetest", "company": "Acme Test Co", "employer_domains": []}],
                  FakeClient({"acmetest": ghost_greenhouse([gh_job(1, "AI Intern")])}))
    a, b = _user(factory, "ia@x.co"), _user(factory, "ib@x.co")
    with session_scope(factory) as s:
        opp = orepo.list_visible(s)[0]
        ap, _ = apps.ensure_interested(s, a.id, opp)
        orepo.save(s, a.id, opp.id)
        orepo.set_not_interested(s, a.id, opp.id, False)
        app_id = ap.id
    with session_scope(factory) as s:
        assert apps.list_for_user(s, b.id) == [] and apps.get(s, b.id, app_id) is None
        assert apps.update(s, b.id, app_id, status="Offer") is False and apps.delete(s, b.id, app_id) is False
        assert orepo.saved_ids(s, b.id) == set() and orepo.list_saved(s, b.id) == []
        orepo.remove_saved(s, b.id, opp.id)                                              # B removing 'their' save must not touch A's
    with session_scope(factory) as s:
        assert orepo.saved_ids(s, a.id) == {opp.id} and apps.get(s, a.id, app_id).status == "Interested"


def test_vector_retrieval_never_crosses_users(app, factory):
    a, b = _user(factory, "va@x.co"), _user(factory, "vb@x.co")
    ra = app.analyse_resume(a.id, "a.pdf", make_pdf(SAMPLE_RESUME))
    rb = app.analyse_resume(b.id, "b.pdf", make_pdf(SAMPLE_RESUME.replace("Priya Test", "Other Person").replace("Document Assistant", "Secret Project Zeta")))
    got = app.store.query("resume", "Secret Project Zeta", 10, {"user_id": a.id, "resume_id": ra.resume_id})
    assert got and all("Zeta" not in p.text for p in got)
    assert all(p.meta["user_id"] == a.id for p in got)


def test_workflow_refuses_other_users_resume(app, factory):
    a, b = _user(factory, "wa@x.co"), _user(factory, "wb@x.co")
    ra = app.analyse_resume(a.id, "a.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    assert app.load(b.id, ra) == (None, None)
    with pytest.raises(PermissionError):
        app.roles(b.id, ra)
    assert app.match_all(b.id, ra) == {}


def test_delete_account_cascades_everything(app, factory):
    u = _user(factory, "d@x.co")
    rid = app.analyse_resume(u.id, "d.pdf", make_pdf(SAMPLE_RESUME)).resume_id
    app.roles(u.id, rid)
    with session_scope(factory) as s:
        apps.create_manual(s, u.id, "Acme", "Intern")
    auth.delete_account(factory, u.id)
    with session_scope(factory) as s:
        for model in (User, ResumeProfile, ExtractedSkill):
            assert s.scalar(select(model)) is None
        assert apps.list_for_user(s, u.id) == []


def test_retention_purges_old_resumes(app, factory):
    u = _user(factory, "ret@x.co")
    app.analyse_resume(u.id, "r.pdf", make_pdf(SAMPLE_RESUME))
    with session_scope(factory) as s:
        assert rrepo.purge_older_than(s, datetime.now(timezone.utc) - timedelta(days=1)) == 0
        assert rrepo.purge_older_than(s, datetime.now(timezone.utc) + timedelta(days=1)) == 1

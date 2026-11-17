from ml.matching import match_opportunity, project_texts
from ml.roles import profile_text, score_roles
from nlp.profile_builder import build_profile
from nlp.skills import find_skills_in_text
from tests.helpers import SAMPLE_RESUME

AI_JD = ("Machine Learning Intern. You will build retrieval-augmented generation (RAG) features with Python, FastAPI and vector databases, "
         "evaluate models with PyTorch and ship services with Docker. Currently pursuing a degree in computer science or AI.")
SALES_JD = "Regional Sales Manager. Manage enterprise accounts, negotiate contracts, travel 50 percent, Excel and CRM reporting. 8+ years of experience in sales."
SENIOR_JD = "Senior Staff Machine Learning Engineer. 8+ years of experience building ML platforms with Python, PyTorch, Kubernetes, AWS and Docker."


def _prep(embedder):
    p, *_ = build_profile(SAMPLE_RESUME)
    roles = score_roles(p, embedder, profile_text(p))
    return p, roles


def _m(p, roles, emb, title, jd, intern):
    return match_opportunity(p, roles, emb, title=title, description=jd, required_skills=find_skills_in_text(f"{title} {jd}"), is_internship=intern)


def test_relevant_internship_outscores_unrelated_job(embedder):
    p, roles = _prep(embedder)
    good = _m(p, roles, embedder, "Machine Learning Intern", AI_JD, True)
    bad = _m(p, roles, embedder, "Regional Sales Manager", SALES_JD, False)
    assert good.score > bad.score + 25
    assert {"Python", "FastAPI", "PyTorch", "Docker"} <= set(good.matched_skills)


def test_scores_are_not_uniformly_high(embedder):
    p, roles = _prep(embedder)
    scores = [_m(p, roles, embedder, t, jd, i).score for t, jd, i in (("ML Intern", AI_JD, True), ("Sales Manager", SALES_JD, False), ("Senior Staff ML Engineer", SENIOR_JD, False))]
    assert min(scores) < 40 and max(scores) - min(scores) > 25


def test_senior_role_with_many_years_is_capped_and_explained(embedder):
    p, roles = _prep(embedder)
    m = _m(p, roles, embedder, "Senior Staff Machine Learning Engineer", SENIOR_JD, False)
    assert m.score <= 35 and m.components["eligibility"] <= 0.15
    assert any("senior" in c.lower() for c in m.concerns) and any("years" in c.lower() for c in m.concerns)


def test_missing_and_weak_skills_reported(embedder):
    p, roles = _prep(embedder)
    m = _m(p, roles, embedder, "Platform Intern", "Intern. Kubernetes, Excel, Python and AWS experience.", True)
    assert "Kubernetes" in m.missing_skills and "AWS" in m.missing_skills
    assert "Excel" in m.weak_skills                 # listed under skills only, not demonstrated
    assert any("Kubernetes" in i for i in m.improvements)


def test_posting_without_skills_shifts_weight_to_semantic(embedder):
    p, roles = _prep(embedder)
    m = match_opportunity(p, roles, embedder, title="Intern", description="Great team and snacks.", required_skills=[], is_internship=True)
    assert m.components["skills"] is None and m.weights_used["skills"] == 0.0 and abs(sum(m.weights_used.values()) - 1.0) < 1e-9
    assert any("doesn't list specific skills" in n for n in m.notes)


def test_graduation_year_mismatch_is_flagged(embedder):
    p, roles = _prep(embedder)
    m = _m(p, roles, embedder, "ML Intern", AI_JD + " Applicants should be graduating in 2026.", True)
    assert any("2026" in c for c in m.concerns)


def test_weights_documented_sum_to_one():
    from config import MATCH_WEIGHTS, ROLE_WEIGHTS
    assert abs(sum(MATCH_WEIGHTS.values()) - 1) < 1e-9 and abs(sum(ROLE_WEIGHTS.values()) - 1) < 1e-9


def test_role_scores_rank_ai_roles_above_sales_like_roles(embedder):
    p, roles = _prep(embedder)
    top = [r.key for r in roles[:5]]
    assert "ai_engineer" in top or "ml_engineer" in top
    r = roles[0]
    assert 0 <= r.score <= 100 and r.explanation and set(r.components) >= {"core_skills", "preferred_skills", "evidence", "semantic"}


def test_embedding_cosine_is_symmetric_and_normalised(embedder):
    a, b = embedder.encode(["python machine learning", "python machine learning model"])
    assert abs((a @ a) - 1) < 1e-5 and abs((a @ b) - (b @ a)) < 1e-6 and a @ b > 0.3
    assert embedder.is_semantic is False and 0 <= embedder.calibrated(0.5) <= 1

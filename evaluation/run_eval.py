"""Run the AI evaluation suite and write docs/EVALUATION.md + evaluation/results.json.

What is measured here is the behaviour of the code on SMALL, SYNTHETIC, HAND-LABELLED FIXTURES. That checks the
pipeline is wired correctly and catches regressions. It is NOT evidence of real-world accuracy. Measures that need a
real LLM (groundedness, structured-output validity) are only run when an LLM is configured and are otherwise
reported as 'not measured'."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from sklearn.metrics import precision_recall_fscore_support  # noqa: E402

from core.llm.base import LLMError  # noqa: E402
from core.llm.providers import get_provider  # noqa: E402
from evaluation.metrics import confusion, micro_set_prf, ndcg_at_k, pairwise_accuracy  # noqa: E402
from ml.embeddings import get_embedder  # noqa: E402
from ml.matching import match_opportunity  # noqa: E402
from ml.roles import profile_text, score_roles  # noqa: E402
from nlp.profile_builder import build_profile  # noqa: E402
from nlp.skills import find_skills_in_text  # noqa: E402
from rag.explain import index_resume, retrieve  # noqa: E402
from rag.store import VectorStore  # noqa: E402

FIX = ROOT / "evaluation" / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def eval_skills(resumes) -> dict:
    pred, gold = [], []
    for r in resumes:
        p, *_ = build_profile(r["text"])
        pred.append({s.name for s in p.skills}); gold.append(set(r["gold_skills"]))
    out = micro_set_prf(pred, gold)
    out["misses"] = {r["id"]: sorted(g - p) for r, p, g in zip(resumes, pred, gold) if g - p}
    out["extras"] = {r["id"]: sorted(p - g) for r, p, g in zip(resumes, pred, gold) if p - g}
    return out


def eval_roles(resumes, emb) -> dict:
    gold, pred, top3 = [], [], 0
    for r in resumes:
        p, *_ = build_profile(r["text"])
        ranked = score_roles(p, emb, profile_text(p))
        gold.append(r["gold_role"]); pred.append(ranked[0].key); top3 += r["gold_role"] in [x.key for x in ranked[:3]]
    pr, rc, f1, _ = precision_recall_fscore_support(gold, pred, average="macro", zero_division=0)
    return {"n": len(resumes), "top1_accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 3), "top3_accuracy": round(top3 / len(gold), 3),
            "macro_precision": round(pr, 3), "macro_recall": round(rc, 3), "macro_f1": round(f1, 3), "confusion": confusion(gold, pred),
            "wrong": {r["id"]: (r["gold_role"], p) for r, p in zip(resumes, pred) if r["gold_role"] != p}}


def eval_matching(resumes, mt, emb) -> dict:
    by_id = {r["id"]: r for r in resumes}
    jobs = {j["id"]: j["text"] for j in mt["jobs"]}
    ndcgs, pw, top1 = [], [], 0
    for rid, rel in mt["relevance"].items():
        p, *_ = build_profile(by_id[rid]["text"])
        roles = score_roles(p, emb, profile_text(p))
        scores = {jid: match_opportunity(p, roles, emb, title=jobs[jid].split(".")[0], description=jobs[jid], required_skills=find_skills_in_text(jobs[jid]), is_internship=True).score for jid in jobs}
        order = sorted(scores, key=lambda j: -scores[j])
        ndcgs.append(ndcg_at_k([rel[j] for j in order], 3)); pw.append(pairwise_accuracy(scores, rel)); top1 += rel[order[0]] == max(rel.values())
    return {"n_resumes": len(mt["relevance"]), "n_jobs": len(jobs), "mean_ndcg_at_3": round(float(np.mean(ndcgs)), 3),
            "mean_pairwise_accuracy": round(float(np.nanmean(pw)), 3), "top1_is_most_relevant": round(top1 / len(mt["relevance"]), 3)}


def eval_retrieval(resumes, rt, emb) -> dict:
    by_id = {r["id"]: r for r in resumes}
    store = VectorStore(emb, force_memory=True)
    hit1 = hit3 = 0
    for i, r in enumerate(resumes, 1):
        p, *_ = build_profile(r["text"]); index_resume(store, 1, i, r["text"], p)
    idx = {r["id"]: i for i, r in enumerate(resumes, 1)}
    for q in rt["queries"]:
        res = store.query("resume", q["query"], 3, {"user_id": 1, "resume_id": idx[q["resume"]]})
        texts = [x.text for x in res]
        hit1 += bool(texts) and q["gold"] in texts[0]; hit3 += any(q["gold"] in t for t in texts)
    n = len(rt["queries"])
    return {"n_queries": n, "hit_at_1": round(hit1 / n, 3), "hit_at_3": round(hit3 / n, 3), "store_backend": store.backend}


def eval_llm(resumes) -> dict:
    try:
        llm = get_provider()
    except LLMError as exc:
        return {"measured": False, "reason": str(exc)}
    if llm is None:
        return {"measured": False, "reason": "No LLM configured (LLM_PROVIDER=none). Structured-output validity and groundedness were NOT measured."}
    from nlp.schemas import LLMProfileEnrichment
    from core.security import wrap_untrusted
    ok = 0
    for r in resumes:
        try:
            llm.complete_json(LLMProfileEnrichment, "Extract resume data. Copy facts only.", wrap_untrusted("resume", r["text"])); ok += 1
        except LLMError:
            pass
    return {"measured": True, "provider": llm.name, "structured_output_valid_rate": round(ok / len(resumes), 3), "n": len(resumes),
            "groundedness": "Measured per explanation at runtime (citation-validity rate stored with each explanation)."}


def main() -> dict:
    resumes = _load("resumes.json")["resumes"]
    emb = get_embedder()
    res = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "embedding_backend": emb.name, "semantic_backend": emb.is_semantic,
           "skills": eval_skills(resumes), "roles": eval_roles(resumes, emb), "matching": eval_matching(resumes, _load("matching.json"), emb),
           "retrieval": eval_retrieval(resumes, _load("retrieval.json"), emb), "llm": eval_llm(resumes)}
    (ROOT / "evaluation" / "results.json").write_text(json.dumps(res, indent=1))
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "EVALUATION.md").write_text(render(res))
    return res


def render(r: dict) -> str:
    s, ro, m, rt, l = r["skills"], r["roles"], r["matching"], r["retrieval"], r["llm"]
    llm_txt = (f"Structured-output valid rate: **{l['structured_output_valid_rate']:.0%}** on {l['n']} fixture resumes via `{l['provider']}`. {l['groundedness']}"
               if l.get("measured") else f"**Not measured.** {l['reason']}")
    return f"""# Evaluation report

Generated {r['generated_at']} · embedding backend: `{r['embedding_backend']}` ({'semantic' if r['semantic_backend'] else 'lexical fallback, NOT deep semantic'})

> **Read this first.** Every number below was measured on **{ro['n']} synthetic, hand-labelled fixture resumes** and a handful of fixture job texts
> that live in `evaluation/fixtures/`. They verify the pipeline works and catch regressions. They are **not** evidence of real-world accuracy:
> the sets are tiny, written by the same author as the rules, and contain no noise from real resumes. No real dataset was used, and no result
> here should be quoted as "the model is X% accurate".
>
> **Why perfect scores in sections 1-2 mean little:** the fixtures were written using the same skill vocabulary the extractor matches, so a
> score of 1.0 is close to circular. It shows the code does what its rules say; it says nothing about resumes phrased differently.

## 1. Skill extraction (rule-based taxonomy + evidence)
Micro precision **{s['precision']}** · recall **{s['recall']}** · F1 **{s['f1']}** (TP {s['tp']}, FP {s['fp']}, FN {s['fn']}).
Misses: `{s['misses']}`; extras: `{s['extras']}`.

## 2. Role recommendation (explainable heuristic, not a trained model)
Top-1 accuracy **{ro['top1_accuracy']}** · top-3 accuracy **{ro['top3_accuracy']}** · macro precision {ro['macro_precision']} / recall {ro['macro_recall']} / F1 {ro['macro_f1']}.
Wrong top-1 cases (gold, predicted): `{ro['wrong']}`.
Confusion matrix labels: `{ro['confusion']['labels']}`; rows = gold, columns = predicted: `{ro['confusion']['matrix']}`.

A supervised scikit-learn classifier was **not** trained: no suitably large, legitimately obtained, labelled resume-to-role dataset was available. `evaluation/role_classifier.py`
contains the experiment and refuses to run below 200 labelled examples rather than report meaningless metrics.

## 3. Semantic matching relevance
{m['n_resumes']} resumes × {m['n_jobs']} jobs, hand-graded relevance (0/1/2). Mean nDCG@3 **{m['mean_ndcg_at_3']}** · pairwise ordering accuracy **{m['mean_pairwise_accuracy']}** · most-relevant job ranked first in **{m['top1_is_most_relevant']:.0%}** of resumes.

## 4. Retrieval relevance (RAG)
{rt['n_queries']} queries over per-user resume chunks (`{rt['store_backend']}` store). Hit@1 **{rt['hit_at_1']}** · Hit@3 **{rt['hit_at_3']}**.

## 5. LLM-dependent measures
{llm_txt}

## Limitations
- Fixtures are synthetic and tiny; results are optimistic by construction.
- With the lexical `hashing-bow` backend, "semantic" similarity is word overlap. Install `requirements-ml.txt` for Sentence Transformers and re-run `python evaluation/run_eval.py`.
- Role requirement profiles are curated by the author, so role scores inherit that author's judgement.
- To get meaningful numbers, add consented, real, labelled resumes and postings to `evaluation/fixtures/` and re-run.
"""


if __name__ == "__main__":
    out = main()
    print(json.dumps({k: v for k, v in out.items() if k in ("skills", "roles", "matching", "retrieval", "llm")}, indent=1)[:3500])

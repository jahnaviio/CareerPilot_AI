# Evaluation report

Generated 2026-11-17T07:36:18+00:00 · embedding backend: `hashing-bow` (lexical fallback, NOT deep semantic)

> **Read this first.** Every number below was measured on **10 synthetic, hand-labelled fixture resumes** and a handful of fixture job texts
> that live in `evaluation/fixtures/`. They verify the pipeline works and catch regressions. They are **not** evidence of real-world accuracy:
> the sets are tiny, written by the same author as the rules, and contain no noise from real resumes. No real dataset was used, and no result
> here should be quoted as "the model is X% accurate".
>
> **Why perfect scores in sections 1-2 mean little:** the fixtures were written using the same skill vocabulary the extractor matches, so a
> score of 1.0 is close to circular. It shows the code does what its rules say; it says nothing about resumes phrased differently.

## 1. Skill extraction (rule-based taxonomy + evidence)
Micro precision **1.0** · recall **1.0** · F1 **1.0** (TP 70, FP 0, FN 0).
Misses: `{}`; extras: `{}`.

## 2. Role recommendation (explainable heuristic, not a trained model)
Top-1 accuracy **1.0** · top-3 accuracy **1.0** · macro precision 1.0 / recall 1.0 / F1 1.0.
Wrong top-1 cases (gold, predicted): `{}`.
Confusion matrix labels: `['ai_automation', 'app_dev', 'data_analyst', 'data_scientist', 'fullstack_dev', 'genai_engineer', 'ml_engineer', 'nlp_engineer', 'python_dev', 'software_dev']`; rows = gold, columns = predicted: `[[1, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 1, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 1]]`.

A supervised scikit-learn classifier was **not** trained: no suitably large, legitimately obtained, labelled resume-to-role dataset was available. `evaluation/role_classifier.py`
contains the experiment and refuses to run below 200 labelled examples rather than report meaningless metrics.

## 3. Semantic matching relevance
5 resumes × 6 jobs, hand-graded relevance (0/1/2). Mean nDCG@3 **0.899** · pairwise ordering accuracy **0.83** · most-relevant job ranked first in **100%** of resumes.

## 4. Retrieval relevance (RAG)
5 queries over per-user resume chunks (`memory` store). Hit@1 **0.8** · Hit@3 **1.0**.

## 5. LLM-dependent measures
**Not measured.** No LLM configured (LLM_PROVIDER=none). Structured-output validity and groundedness were NOT measured.

## Limitations
- Fixtures are synthetic and tiny; results are optimistic by construction.
- With the lexical `hashing-bow` backend, "semantic" similarity is word overlap. Install `requirements-ml.txt` for Sentence Transformers and re-run `python evaluation/run_eval.py`.
- Role requirement profiles are curated by the author, so role scores inherit that author's judgement.
- To get meaningful numbers, add consented, real, labelled resumes and postings to `evaluation/fixtures/` and re-run.

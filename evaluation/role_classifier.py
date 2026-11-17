"""Supervised role-classifier experiment (scikit-learn). Requires a REAL labelled dataset: JSONL with
{"text": "<resume text>", "role": "<role key>"} lines, collected with consent. It deliberately refuses to run on
small data, because metrics from a handful of examples would be misleading. Nothing here fabricates data."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_EXAMPLES = 200


class InsufficientData(ValueError):
    pass


def run(path: str, test_size: float = 0.25, seed: int = 7) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline

    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    if len(rows) < MIN_EXAMPLES:
        raise InsufficientData(f"{len(rows)} labelled examples found; at least {MIN_EXAMPLES} are required for a meaningful held-out evaluation.")
    X, y = [r["text"] for r in rows], [r["role"] for r in rows]
    if min(y.count(c) for c in set(y)) < 4:
        raise InsufficientData("Every role needs at least 4 examples for a stratified split.")
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=test_size, random_state=seed, stratify=y)   # strict train/test separation
    clf = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True), LogisticRegression(max_iter=1000, class_weight="balanced"))
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    return {"n_train": len(Xtr), "n_test": len(Xte), "report": classification_report(yte, pred, output_dict=True, zero_division=0),
            "confusion_labels": sorted(set(y)), "confusion": confusion_matrix(yte, pred, labels=sorted(set(y))).tolist()}


if __name__ == "__main__":
    try:
        print(json.dumps(run(sys.argv[1]), indent=1))
    except (InsufficientData, IndexError, FileNotFoundError) as exc:
        print(f"Cannot run: {exc}\nUsage: python evaluation/role_classifier.py labelled_resumes.jsonl")
        raise SystemExit(2)

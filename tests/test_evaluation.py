import json
import pytest

from evaluation import metrics, role_classifier, run_eval


def test_metric_functions():
    assert metrics.prf(8, 2, 2) == {"precision": 0.8, "recall": 0.8, "f1": 0.8}
    assert metrics.ndcg_at_k([2, 1, 0], 3) == pytest.approx(1.0) and metrics.ndcg_at_k([0, 1, 2], 3) < 1.0
    assert metrics.confusion(["a", "b"], ["a", "a"])["matrix"] == [[1, 0], [1, 0]]
    assert metrics.pairwise_accuracy({"x": 3, "y": 1}, {"x": 2, "y": 0}) == 1.0


def test_evaluation_runs_and_reports_unmeasured_llm_honestly(tmp_path):
    res = run_eval.main()
    assert res["llm"]["measured"] is False and "NOT measured" in res["llm"]["reason"]
    assert 0 <= res["roles"]["top1_accuracy"] <= 1 and res["retrieval"]["n_queries"] == 5
    md = (run_eval.ROOT / "docs" / "EVALUATION.md").read_text()
    assert "synthetic" in md.lower() and "evidence of real-world accuracy" in md.lower() and "**not**" in md


def test_fixtures_are_labelled_synthetic():
    for f in ("resumes.json", "matching.json", "retrieval.json"):
        assert "SYNTHETIC" in json.loads((run_eval.FIX / f).read_text())["_note"].upper()


def test_classifier_refuses_tiny_datasets(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text("\n".join(json.dumps({"text": f"python {i}", "role": "ai_engineer"}) for i in range(10)))
    with pytest.raises(role_classifier.InsufficientData):
        role_classifier.run(str(p))

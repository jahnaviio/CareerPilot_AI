from __future__ import annotations

import math
from collections import Counter


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def micro_set_prf(pred: list[set], gold: list[set]) -> dict:
    tp = sum(len(p & g) for p, g in zip(pred, gold))
    fp = sum(len(p - g) for p, g in zip(pred, gold))
    fn = sum(len(g - p) for p, g in zip(pred, gold))
    return {**prf(tp, fp, fn), "tp": tp, "fp": fp, "fn": fn}


def ndcg_at_k(ranked_rel: list[int], k: int) -> float:
    dcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ranked_rel[:k]))
    ideal = sorted(ranked_rel, reverse=True)
    idcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ideal[:k]))
    return dcg / idcg if idcg else 0.0


def confusion(gold: list[str], pred: list[str]) -> dict:
    labels = sorted(set(gold) | set(pred))
    c = Counter(zip(gold, pred))
    return {"labels": labels, "matrix": [[c[(g, p)] for p in labels] for g in labels]}


def pairwise_accuracy(scores: dict[str, float], rel: dict[str, int]) -> float:
    ok = tot = 0
    for a in rel:
        for b in rel:
            if rel[a] > rel[b]:
                tot += 1
                ok += scores[a] > scores[b]
    return ok / tot if tot else float("nan")

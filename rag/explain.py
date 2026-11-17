"""Evidence-grounded explanations via RAG.

Flow: index the user's resume chunks (user-scoped) and the posting's chunks -> retrieve the passages most
relevant to the question -> ask the LLM to answer using ONLY those numbered passages, citing ids -> validate:
claims that cite no real passage id are dropped. Without an LLM, an extractive explanation is built from the
same retrieved passages and the match detail, so the feature still works."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from core.llm.base import LLMError, LLMProvider
from core.security import wrap_untrusted
from ml.embeddings import chunk_text
from nlp.schemas import ResumeProfile
from rag.store import Passage, VectorStore


class Claim(BaseModel):
    text: str
    cites: list[str] = Field(default_factory=list)


class GroundedExplanation(BaseModel):
    summary: str = ""
    strengths: list[Claim] = Field(default_factory=list)
    gaps: list[Claim] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


def resume_chunks(raw_text: str, profile: ResumeProfile) -> list[tuple[str, str]]:
    chunks = []
    for pr in profile.projects:
        chunks.append((f"project:{pr.title[:40]}", f"Project {pr.title}: {pr.description} Technologies: {', '.join(pr.technologies)}"))
    for e in profile.experience:
        chunks.append((f"exp:{e.role[:40]}", f"{e.role} ({e.period}): {' '.join(e.bullets)}"))
    if profile.skills:
        chunks.append(("skills", "Skills: " + ", ".join(s.name for s in profile.skills)))
    for i, c in enumerate(chunk_text(raw_text)):
        chunks.append((f"text:{i}", c))
    return [(n, t) for n, t in chunks if t.strip()]


def index_resume(store: VectorStore, user_id: int, resume_id: int, raw_text: str, profile: ResumeProfile) -> int:
    store.delete("resume", {"user_id": user_id, "resume_id": resume_id})
    items = resume_chunks(raw_text, profile)
    store.add("resume", [f"u{user_id}-r{resume_id}-{i}" for i in range(len(items))], [t for _, t in items],
              [{"user_id": user_id, "resume_id": resume_id, "label": n} for n, _ in items])
    return len(items)


def index_opportunity(store: VectorStore, opp_id: int, title: str, description: str) -> int:
    store.delete("opportunity", {"opportunity_id": opp_id})
    chunks = chunk_text(f"{title}\n{description}")
    store.add("opportunity", [f"o{opp_id}-{i}" for i in range(len(chunks))], chunks, [{"opportunity_id": opp_id}] * len(chunks))
    return len(chunks)


def retrieve(store: VectorStore, user_id: int, resume_id: int, opp_id: int, title: str, k: int = 4) -> tuple[list[Passage], list[Passage]]:
    r = store.query("resume", f"Experience and projects relevant to: {title}", k, {"user_id": user_id, "resume_id": resume_id})
    j = store.query("opportunity", f"Requirements and responsibilities for {title}", k, {"opportunity_id": opp_id})
    return r, j


def explain(store: VectorStore, llm: LLMProvider | None, *, user_id: int, resume_id: int, opp_id: int, title: str, company: str,
            match: dict) -> dict:
    r_pass, j_pass = retrieve(store, user_id, resume_id, opp_id, title)
    ids = {f"R{i+1}": p for i, p in enumerate(r_pass)} | {f"J{i+1}": p for i, p in enumerate(j_pass)}
    base = _extractive(match, ids)
    base["retrieval_backend"] = store.backend
    if llm is None:
        base["mode"] = "extractive"
        return base
    ctx = "\n".join(f"[{k}] {p.text[:600]}" for k, p in ids.items())
    try:
        g = llm.complete_json(
            GroundedExplanation,
            "You explain why a candidate does or does not fit a role. Use ONLY the numbered passages. R* = candidate resume, J* = job posting. "
            "Every strength and gap must cite passage ids in 'cites'. Do not invent skills, experience or requirements. "
            "Be honest about gaps. Do not promise outcomes.",
            f"Role: {title} at {company}\nComputed match: score {match.get('score')}, matched skills {match.get('matched_skills')}, "
            f"missing skills {match.get('missing_skills')}, concerns {match.get('concerns')}\n\n"
            + wrap_untrusted("passages", ctx))
    except LLMError as exc:
        base["mode"] = "extractive"
        base["llm_error"] = str(exc)
        return base
    valid = lambda cl: [c for c in cl if c.cites and all(x in ids for x in c.cites)]
    strengths, gaps = valid(g.strengths), valid(g.gaps)
    dropped = (len(g.strengths) - len(strengths)) + (len(g.gaps) - len(gaps))
    return {"mode": "llm_grounded", "summary": g.summary[:600], "strengths": [c.model_dump() for c in strengths],
            "gaps": [c.model_dump() for c in gaps], "next_steps": g.next_steps[:4],
            "passages": {k: p.text[:400] for k, p in ids.items()}, "dropped_ungrounded_claims": dropped,
            "groundedness": 1.0 if (strengths or gaps) and dropped == 0 else (round(1 - dropped / max(1, dropped + len(strengths) + len(gaps)), 2)),
            "retrieval_backend": store.backend}


def _extractive(match: dict, ids: dict[str, Passage]) -> dict:
    strengths, gaps = [], []
    r_ids = [k for k in ids if k.startswith("R")]
    if match.get("matched_skills"):
        strengths.append({"text": f"You already show: {', '.join(match['matched_skills'][:8])}.", "cites": r_ids[:2]})
    for pr in match.get("relevant_projects", []):
        strengths.append({"text": f"Your project '{pr['project']}' is the closest to this posting.", "cites": r_ids[:1]})
    if match.get("missing_skills"):
        gaps.append({"text": f"The posting asks for skills not found on your resume: {', '.join(match['missing_skills'][:8])}.", "cites": [k for k in ids if k.startswith("J")][:2]})
    for c in match.get("concerns", []):
        gaps.append({"text": c, "cites": [k for k in ids if k.startswith("J")][:1]})
    return {"mode": "extractive", "summary": "", "strengths": strengths, "gaps": gaps, "next_steps": match.get("improvements", []),
            "passages": {k: p.text[:400] for k, p in ids.items()}, "groundedness": None}

"""Orchestrated workflow with six components and typed hand-offs:

  1 ResumeAnalysis        bytes -> validated ResumeProfile (+ quality report)
  2 CareerRecommendation  ResumeProfile -> ranked RoleRecommendations
  3 SkillGapAnalysis      (profile, role) -> gaps / roadmap
  4 OpportunityDiscovery  registry -> verified Opportunity rows (ingestion)
  5 OpportunityMatching   (profile, roles, opportunities) -> MatchResults
  6 ApplicationAssistance (profile, opportunity) -> grounded explanation / tailored resume / cover letter

This is a deterministic pipeline whose components exchange validated structures. LLM calls happen only inside
components 1 and 6, behind a provider interface, with output validation. It is not an autonomous multi-agent system."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from config import settings
from core.db import session_scope
from core.llm.base import LLMError, LLMProvider
from core.llm.providers import get_provider
from core.security import clean_untrusted_text, detect_injection, safe_filename, validate_upload, wrap_untrusted, UNTRUSTED_NOTICE
from ml.embeddings import Embedder, get_embedder
from ml.matching import MatchResult, match_opportunity, project_texts
from ml.roles import RoleRecommendation, profile_text, score_roles
from nlp.extract import ExtractionError, extract_text
from nlp.profile_builder import build_profile
from nlp.quality import analyse_quality
from nlp.schemas import ResumeProfile
from nlp.skills import find_skills_in_text
from rag import explain as rag
from rag.store import VectorStore
from repositories import opportunities as opp_repo
from repositories import resumes as resume_repo
from services import analysis, auth
from services.ingestion import IngestSummary, load_registry, run_ingestion

log = logging.getLogger(__name__)


class QuotaExceeded(RuntimeError):
    pass


class FeatureUnavailable(RuntimeError):
    """The feature needs an LLM and none is configured / reachable."""


@dataclass
class UploadResult:
    resume_id: int | None = None
    reused: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str = ""


class CareerPilot:
    def __init__(self, factory: sessionmaker, *, embedder: Embedder | None = None, store: VectorStore | None = None,
                 llm: LLMProvider | None | str = "auto"):
        self.factory = factory
        self.embedder = embedder or get_embedder()
        self.store = store or VectorStore(self.embedder)
        self._llm_cfg_error = ""
        if llm == "auto":
            try:
                llm = get_provider()
            except LLMError as exc:
                self._llm_cfg_error, llm = str(exc), None
        self.llm: LLMProvider | None = llm  # type: ignore[assignment]
        self._vec_cache: dict[tuple, object] = {}

    # ---------- 1. Resume analysis ----------
    def analyse_resume(self, user_id: int, filename: str, data: bytes) -> UploadResult:
        ext, err = validate_upload(filename, data, settings.max_upload_mb)
        if err:
            return UploadResult(error=err)
        digest = hashlib.sha256(data).hexdigest()
        with session_scope(self.factory) as s:
            existing = resume_repo.find_by_hash(s, user_id, digest)
            if existing:  # avoid repeated processing of the same file
                resume_repo.activate(s, user_id, existing.id)
                return UploadResult(resume_id=existing.id, reused=True)
        try:
            doc = extract_text(data, ext)
        except ExtractionError as exc:
            return UploadResult(error=str(exc))
        except Exception:
            log.exception("Unexpected extraction failure")  # no resume content in logs
            return UploadResult(error="Could not read this file. Try exporting it again as PDF or DOCX.")
        llm = self.llm if self._allow(user_id) else None
        profile, method, warns = build_profile(doc.text, llm)
        warns = doc.warnings + warns
        with session_scope(self.factory) as s:
            r = resume_repo.add(s, user_id, safe_filename(filename), digest, doc.text, profile, method)
            rid = r.id
        rag.index_resume(self.store, user_id, rid, doc.text, profile)
        return UploadResult(resume_id=rid, warnings=warns)

    def _allow(self, user_id: int) -> bool:
        if self.llm is None:
            return False
        ok, _ = auth.allow_ai_call(self.factory, user_id)
        return ok

    def load(self, user_id: int, resume_id: int | None = None):
        with session_scope(self.factory) as s:
            r = resume_repo.get(s, user_id, resume_id) if resume_id else resume_repo.get_active(s, user_id)
            if r is None:
                return None, None
            return r, ResumeProfile.model_validate(r.profile)

    def update_profile(self, user_id: int, resume_id: int, profile: ResumeProfile) -> bool:
        with session_scope(self.factory) as s:
            ok = resume_repo.save_corrected_profile(s, user_id, resume_id, profile)
            r = resume_repo.get(s, user_id, resume_id)
            raw = r.raw_text if r else ""
        if ok:
            rag.index_resume(self.store, user_id, resume_id, raw, profile)
        return ok

    def quality(self, user_id: int, resume_id: int) -> dict:
        return self._cached(user_id, resume_id, "quality", lambda r, p: analyse_quality(p, r.raw_text))

    # ---------- 2. Career recommendation ----------
    def roles(self, user_id: int, resume_id: int) -> list[RoleRecommendation]:
        def compute(r, p):
            return {"roles": [asdict(x) for x in score_roles(p, self.embedder, profile_text(p) or r.raw_text)], "backend": self.embedder.name}
        data = self._cached(user_id, resume_id, "roles", compute)
        return [RoleRecommendation(**d) for d in data["roles"]]

    # ---------- 3. Skill gap ----------
    def skill_gap(self, user_id: int, resume_id: int, role_key: str) -> dict:
        _, p = self.load(user_id, resume_id)
        return analysis.skill_gap(p, role_key)

    def roadmap(self, user_id: int, resume_id: int, role_key: str, days: int) -> dict:
        r, p = self.load(user_id, resume_id)
        q = self.quality(user_id, resume_id)
        return self._cached(user_id, resume_id, f"roadmap:{role_key}:{days}", lambda *_: analysis.roadmap(p, role_key, days, q["issues"]))

    def roadmap_progress(self, user_id: int, resume_id: int, role_key: str, days: int) -> dict:
        with session_scope(self.factory) as s:
            row = resume_repo.get_analysis(s, user_id, resume_id, f"progress:{role_key}:{days}")
            return dict(row.payload) if row else {}

    def set_roadmap_task(self, user_id: int, resume_id: int, role_key: str, days: int, task_id: str, done: bool) -> None:
        cur = self.roadmap_progress(user_id, resume_id, role_key, days)
        cur[task_id] = done
        with session_scope(self.factory) as s:
            resume_repo.set_analysis(s, user_id, resume_id, f"progress:{role_key}:{days}", cur)

    def readiness(self, user_id: int, resume_id: int) -> dict:
        return analysis.readiness(self.roles(user_id, resume_id))

    CACHE_VERSION = "v2"   # bump when the wording/shape of saved analyses changes; older saved results are then recomputed

    def _cached(self, user_id: int, resume_id: int, kind: str, compute) -> dict:
        kind = f"{kind}@{self.CACHE_VERSION}"
        with session_scope(self.factory) as s:
            row = resume_repo.get_analysis(s, user_id, resume_id, kind)
            if row:
                return row.payload
            r = resume_repo.get(s, user_id, resume_id)
            if r is None:
                raise PermissionError("Resume not found")
            payload = compute(r, ResumeProfile.model_validate(r.profile))
            resume_repo.set_analysis(s, user_id, resume_id, kind, payload)
            return payload

    # ---------- 4. Opportunity discovery ----------
    def refresh_opportunities(self, entries: list[dict] | None = None) -> IngestSummary:
        return run_ingestion(self.factory, entries if entries is not None else load_registry())

    # ---------- 5. Opportunity matching ----------
    def match_all(self, user_id: int, resume_id: int, internship: bool | None = None, force: bool = False) -> dict[int, dict]:
        r, p = self.load(user_id, resume_id)
        if r is None:
            return {}
        roles = self.roles(user_id, resume_id)
        with session_scope(self.factory) as s:
            opps = opp_repo.list_visible(s, internship=internship)
            existing = {} if force else opp_repo.matches_for(s, user_id, resume_id)
            todo = [o for o in opps if o.id not in existing]
            pvec = self.embedder.encode([profile_text(p) or " "])[0]
            ptexts = project_texts(p)
            pvecs = list(zip([n for n, _ in ptexts], self.embedder.encode([t for _, t in ptexts]))) if ptexts else []
            docs = [f"{o.title}\n{o.description[:3500]}" for o in todo]
            jvecs = self.embedder.encode(docs) if docs else []
            for o, jv in zip(todo, jvecs):
                m = match_opportunity(p, roles, self.embedder, title=o.title, description=o.description, required_skills=o.required_skills,
                                      is_internship=o.is_internship, profile_vec=pvec, project_vecs=pvecs, job_vec=jv)
                opp_repo.upsert_match(s, user_id, resume_id, o.id, m.score, m.to_dict())
            return {oid: {"score": m.score, **m.detail} for oid, m in opp_repo.matches_for(s, user_id, resume_id).items()}

    # ---------- 6. Application assistance ----------
    def explain_match(self, user_id: int, resume_id: int, opp_id: int) -> dict:
        r, p = self.load(user_id, resume_id)
        with session_scope(self.factory) as s:
            o = opp_repo.get(s, opp_id)
            m = opp_repo.matches_for(s, user_id, resume_id).get(opp_id)
            if r is None or o is None or m is None:
                raise PermissionError("Match not available")
            title, company, desc, detail = o.title, o.company, o.description, {"score": m.score, **m.detail}
            cached = resume_repo.get_analysis(s, user_id, resume_id, f"explanation:{opp_id}")
            if cached:
                return cached.payload
        rag.index_resume(self.store, user_id, resume_id, r.raw_text, p)   # idempotent; keeps retrieval working after a restart with a non-persistent store
        rag.index_opportunity(self.store, opp_id, title, desc)
        use_llm = self._allow(user_id)
        out = rag.explain(self.store, self.llm if use_llm else None, user_id=user_id, resume_id=resume_id, opp_id=opp_id, title=title, company=company, match=detail)
        with session_scope(self.factory) as s:
            resume_repo.set_analysis(s, user_id, resume_id, f"explanation:{opp_id}", out, provider=out.get("mode", ""))
        return out

    def _require_llm(self, user_id: int) -> LLMProvider:
        if self.llm is None:
            raise FeatureUnavailable(self._llm_cfg_error or "This feature needs an AI provider. Set LLM_PROVIDER and its credentials (see README).")
        ok, msg = auth.allow_ai_call(self.factory, user_id)
        if not ok:
            raise QuotaExceeded(msg)
        return self.llm

    def tailor_resume(self, user_id: int, resume_id: int, opp_id: int) -> dict:
        llm = self._require_llm(user_id)
        r, p = self.load(user_id, resume_id)
        with session_scope(self.factory) as s:
            o = opp_repo.get(s, opp_id)
            if r is None or o is None:
                raise PermissionError("Not found")
            title, company, desc = o.title, o.company, o.description
        try:
            text = llm.complete(
                "You are an ATS resume editor. Rewrite the candidate's resume for the target role. STRICT RULES: use only facts present in the "
                "resume; never add skills, tools, employers, projects, dates, numbers or certifications that are not in it; keep the name, education and "
                f"contact details; reorder and rephrase to emphasise relevant real experience; output plain text only. {UNTRUSTED_NOTICE}",
                f"Target role: {title} at {company}\n\n{wrap_untrusted('job_posting', desc[:4000])}\n\n{wrap_untrusted('resume', r.raw_text)}", max_tokens=2000)
        except LLMError as exc:
            raise FeatureUnavailable(str(exc)) from exc
        text = clean_untrusted_text(text)
        added = sorted(set(find_skills_in_text(text)) - {s.name for s in p.skills} - set(find_skills_in_text(r.raw_text)))
        return {"text": text, "unsupported_skills": added,
                "warning": (f"The draft mentions skills that are not on your resume: {', '.join(added)}. Remove them before using it." if added else "")}

    def cover_letter(self, user_id: int, resume_id: int, opp_id: int) -> dict:
        llm = self._require_llm(user_id)
        r, p = self.load(user_id, resume_id)
        with session_scope(self.factory) as s:
            o = opp_repo.get(s, opp_id)
            m = opp_repo.matches_for(s, user_id, resume_id).get(opp_id)
            if r is None or o is None:
                raise PermissionError("Not found")
            title, company, desc = o.title, o.company, o.description
            matched = (m.detail.get("matched_skills") if m else []) or []
        try:
            text = llm.complete(
                "You write concise, honest cover letters (max 250 words, 3 short paragraphs). Use ONLY facts in the resume. Never invent experience, "
                f"numbers or enthusiasm for facts not given. No placeholders except the candidate's name if unknown. {UNTRUSTED_NOTICE}",
                f"Role: {title} at {company}\nSkills the resume shares with the posting: {matched}\n\n{wrap_untrusted('job_posting', desc[:3500])}\n\n{wrap_untrusted('resume', r.raw_text)}",
                max_tokens=700)
        except LLMError as exc:
            raise FeatureUnavailable(str(exc)) from exc
        text = clean_untrusted_text(text)
        added = sorted(set(find_skills_in_text(text)) - set(find_skills_in_text(r.raw_text)))
        return {"text": text, "unsupported_skills": added,
                "warning": (f"The letter mentions skills not on your resume: {', '.join(added)}. Edit before sending." if added else "")}


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

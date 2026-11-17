"""Role catalogue and the explainable role-suitability score.

Role requirements below are CURATED PROFILES written for this project (what such roles typically ask for),
not data scraped from vacancies, and the score is a transparent heuristic, NOT a validated probability.

score = 100 * ( 0.45 * core_coverage + 0.15 * preferred_coverage + 0.15 * evidence_strength + 0.25 * semantic )
  core/preferred coverage : demonstrated skill = 1.0, skill only listed = 0.6, absent = 0
  evidence_strength       : share of the role-relevant skills you hold that are demonstrated in projects/experience
  semantic                : calibrated cosine(resume text, role description) from the active embedding backend
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config import ROLE_WEIGHTS
from ml.embeddings import Embedder
from nlp.schemas import ResumeProfile


@dataclass(frozen=True)
class RoleDef:
    key: str
    title: str
    description: str
    core: tuple[str, ...]
    preferred: tuple[str, ...]
    keywords: tuple[str, ...] = ()  # title keywords used to align opportunities to this role


ROLES: list[RoleDef] = [
    RoleDef("ai_engineer", "AI Engineer",
            "Builds and ships AI-powered applications: integrates LLMs and ML models into products, builds APIs and data pipelines, evaluates model quality, and deploys services.",
            ("Python", "Machine Learning", "REST APIs", "Git"),
            ("LLMs", "Docker", "FastAPI", "PyTorch", "RAG", "SQL", "AWS", "Deep Learning"),
            ("ai engineer", "artificial intelligence", "applied ai", "ai/ml", "ai software")),
    RoleDef("genai_engineer", "Generative AI Engineer",
            "Builds applications on large language models: prompt engineering, retrieval-augmented generation, embeddings and vector search, agents and tool use, and LLM evaluation.",
            ("Python", "LLMs", "Prompt Engineering", "RAG"),
            ("Embeddings", "Vector Databases", "LangChain", "AI Agents", "FastAPI", "Hugging Face", "Fine-tuning", "Docker"),
            ("generative ai", "genai", "gen ai", "llm", "prompt", "agent")),
    RoleDef("ml_engineer", "Machine Learning Engineer",
            "Trains, evaluates and deploys machine learning models: feature engineering, model selection, experiment tracking, and productionising models with reliable pipelines.",
            ("Python", "Machine Learning", "Scikit-learn", "Statistics"),
            ("PyTorch", "TensorFlow", "Pandas", "NumPy", "Feature Engineering", "Docker", "MLflow", "SQL", "Deep Learning"),
            ("machine learning", "ml engineer", "mlops", "ml ")),
    RoleDef("nlp_engineer", "NLP Engineer",
            "Builds language understanding systems: text classification, named entity recognition, embeddings, transformers, information extraction and search relevance.",
            ("Python", "Natural Language Processing", "Machine Learning"),
            ("Transformers", "Hugging Face", "PyTorch", "Embeddings", "Deep Learning", "Scikit-learn", "LLMs"),
            ("nlp", "natural language", "language model", "speech", "text")),
    RoleDef("llm_engineer", "LLM Engineer",
            "Works directly with large language models: inference and serving, fine-tuning, prompt and evaluation pipelines, retrieval systems and cost/latency optimisation.",
            ("Python", "LLMs", "Transformers"),
            ("Fine-tuning", "PyTorch", "Hugging Face", "RAG", "Embeddings", "Docker", "Deep Learning"),
            ("llm", "language model", "foundation model", "inference")),
    RoleDef("ai_automation", "AI Automation Engineer",
            "Automates business workflows with AI: connects LLMs to tools and APIs, builds agentic workflows, integrates SaaS systems and monitors reliability.",
            ("Python", "REST APIs", "LLMs", "AI Agents"),
            ("Prompt Engineering", "FastAPI", "Docker", "SQL", "JavaScript", "Git", "Authentication"),
            ("automation", "agent", "workflow", "integration")),
    RoleDef("python_dev", "Python Developer",
            "Builds backend services and tools in Python: web frameworks, databases, APIs, testing and deployment.",
            ("Python", "SQL", "Git", "REST APIs"),
            ("FastAPI", "Flask", "Django", "PostgreSQL", "Docker", "Software Testing", "Linux", "Object-Oriented Programming"),
            ("python", "backend")),
    RoleDef("software_dev", "Software Developer",
            "Designs, builds and tests software: data structures and algorithms, object-oriented design, databases, version control, and collaborative engineering practice.",
            ("Data Structures and Algorithms", "Git", "Object-Oriented Programming"),
            ("Python", "Java", "SQL", "REST APIs", "Software Testing", "Docker", "Linux", "System Design", "DBMS"),
            ("software engineer", "software developer", "sde", "swe", "software development")),
    RoleDef("fullstack_dev", "Full-Stack Developer",
            "Builds complete web applications: responsive front-ends, back-end APIs, databases, authentication and deployment.",
            ("JavaScript", "HTML", "CSS", "REST APIs", "SQL"),
            ("React", "Node.js", "TypeScript", "Next.js", "PostgreSQL", "MongoDB", "Git", "Docker", "Authentication", "Tailwind CSS"),
            ("full stack", "full-stack", "fullstack", "web developer", "frontend", "front-end")),
    RoleDef("app_dev", "Application Developer",
            "Develops and maintains business applications and enterprise platforms: configuring and customising platforms, integrating APIs, writing business logic and supporting users.",
            ("SQL", "Object-Oriented Programming", "REST APIs"),
            ("Java", "Salesforce", "Python", "JavaScript", "Git", "DBMS", "Agile", "Software Testing"),
            ("application developer", "applications engineer", "salesforce", "developer")),
    RoleDef("data_analyst", "Data Analyst",
            "Turns data into decisions: SQL querying, cleaning and analysis, dashboards and clear communication of findings.",
            ("SQL", "Excel", "Data Analysis", "Data Visualization"),
            ("Python", "Pandas", "Power BI", "Tableau", "Statistics", "Matplotlib"),
            ("data analyst", "analytics", "business analyst", "bi ")),
    RoleDef("data_scientist", "Data Scientist",
            "Applies statistics and machine learning to business problems: exploratory analysis, modelling, experimentation and communicating results.",
            ("Python", "Statistics", "Machine Learning", "Pandas"),
            ("SQL", "Scikit-learn", "NumPy", "Data Visualization", "A/B Testing", "Feature Engineering", "Deep Learning"),
            ("data scientist", "data science", "research scientist", "applied scientist")),
]
ROLE_BY_KEY = {r.key: r for r in ROLES}


@dataclass
class RoleRecommendation:
    key: str
    title: str
    score: int
    matching_skills: list[str]
    missing_core: list[str]
    missing_preferred: list[str]
    limited_evidence: list[str]
    evidence: list[dict]            # [{skill, line}]
    components: dict[str, float]
    explanation: str
    next_steps: list[str]
    tier: str                       # "ready" | "close" | "needs_work"


def _cov(skills: dict, required: tuple[str, ...]) -> tuple[float, list[str], list[str], list[str]]:
    got, missing, weak = 0.0, [], []
    have = []
    for r in required:
        s = skills.get(r.lower())
        if s is None:
            missing.append(r)
        else:
            have.append(r)
            if s.strength == "demonstrated":
                got += 1.0
            else:
                got += 0.6
                weak.append(r)
    return (got / len(required) if required else 0.0), have, missing, weak


def profile_text(p: ResumeProfile) -> str:
    parts = [p.summary, " ".join(p.skill_names())]
    for pr in p.projects:
        parts.append(f"{pr.title}. {pr.description} {' '.join(pr.technologies)}")
    for e in p.experience:
        parts.append(f"{e.role}. {' '.join(e.bullets)}")
    return "\n".join(x for x in parts if x).strip()


def score_roles(p: ResumeProfile, embedder: Embedder, resume_text: str | None = None) -> list[RoleRecommendation]:
    skills = p.skill_map()
    text = resume_text or profile_text(p)
    vecs = embedder.encode([text] + [r.description for r in ROLES]) if text else None
    out: list[RoleRecommendation] = []
    for i, role in enumerate(ROLES):
        core_cov, core_have, core_miss, core_weak = _cov(skills, role.core)
        pref_cov, pref_have, pref_miss, pref_weak = _cov(skills, role.preferred)
        relevant = core_have + pref_have
        demo = [s for s in relevant if skills[s.lower()].strength == "demonstrated"]
        evidence = len(demo) / len(relevant) if relevant else 0.0
        cos = float(vecs[0] @ vecs[i + 1]) if vecs is not None else 0.0
        sem = embedder.calibrated(cos)
        w = ROLE_WEIGHTS
        score = 100 * (w["core_skills"] * core_cov + w["preferred_skills"] * pref_cov + w["evidence"] * evidence + w["semantic"] * sem)
        ev = []
        for s in relevant:
            for line in skills[s.lower()].evidence[:1]:
                ev.append({"skill": s, "line": line})
        tier = "ready" if score >= 65 and not core_miss else ("close" if score >= 40 else "needs_work")
        steps = [f"Build a small project that uses {m} and describe the result on your resume." for m in core_miss[:2]]
        steps += [f"Show {w_} in a project or internship bullet; right now it is only listed under skills." for w_ in core_weak[:1]]
        if not steps and pref_miss:
            steps.append(f"Add depth with {pref_miss[0]} to stand out for {role.title} roles.")
        expl = (f"You show {len(core_have)} of {len(role.core)} must-have skills and {len(pref_have)} of {len(role.preferred)} nice-to-have skills. "
                f"{len(demo)} of your {len(relevant)} matching skills are backed by your projects or work.")
        out.append(RoleRecommendation(role.key, role.title, int(round(score)), relevant, core_miss, pref_miss, core_weak + pref_weak,
                                      ev[:6], {"core_skills": round(core_cov, 2), "preferred_skills": round(pref_cov, 2),
                                               "evidence": round(evidence, 2), "semantic": round(sem, 2), "raw_cosine": round(cos, 3)},
                                      expl, steps[:3], tier))
    return sorted(out, key=lambda r: -r.score)

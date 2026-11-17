"""Central, environment-driven configuration. No other module reads os.environ."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Some Windows setups (Smart App Control / Application Control) block SQLAlchemy's compiled speed-up file.
# SQLAlchemy 2.0 works fine without it, so never even try to load it. Must be set before sqlalchemy is imported.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{(DATA_DIR / 'careerpilot.db').as_posix()}"
    # Render/Heroku style URLs use the legacy "postgres://" scheme.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


@dataclass(frozen=True)
class Settings:
    app_name: str = "CareerPilot AI"
    app_env: str = os.getenv("APP_ENV", "development")  # development | production
    database_url: str = field(default_factory=_database_url)

    # ---- LLM (one provider interface; see core/llm) ----
    llm_provider: str = os.getenv("LLM_PROVIDER", "none").strip().lower()  # none|ollama|openai_compatible|anthropic
    llm_model: str = os.getenv("LLM_MODEL", "").strip()
    llm_base_url: str = os.getenv("LLM_BASE_URL", "").strip()  # openai_compatible only
    llm_api_key: str = os.getenv("LLM_API_KEY", "").strip()
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    llm_timeout_s: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))

    # ---- Embeddings / retrieval ----
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "auto")  # auto|sentence_transformers|hashing
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    chroma_dir: str = os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma"))
    vector_backend: str = os.getenv("VECTOR_BACKEND", "auto")  # auto (Chroma if installed) | chroma | memory

    # ---- Uploads / privacy ----
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "5"))
    max_resume_pages: int = int(os.getenv("MAX_RESUME_PAGES", "10"))
    ocr_enabled: bool = _bool("OCR_ENABLED", False)
    resume_retention_days: int = int(os.getenv("RESUME_RETENTION_DAYS", "90"))

    # ---- Security ----
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "24"))
    login_max_attempts: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    login_lockout_minutes: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
    ai_calls_per_hour: int = int(os.getenv("AI_CALLS_PER_HOUR", "40"))

    # ---- Opportunity ingestion ----
    source_registry_path: str = os.getenv("SOURCE_REGISTRY_PATH", str(BASE_DIR / "opportunities" / "company_registry.yaml"))
    http_timeout_s: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
    http_min_interval_s: float = float(os.getenv("HTTP_MIN_INTERVAL_SECONDS", "1.0"))
    http_user_agent: str = os.getenv("HTTP_USER_AGENT", "CareerPilotAI/1.0 (+student career tool; contact: set HTTP_USER_AGENT)")
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "").strip()
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "").strip()
    stale_after_hours: int = int(os.getenv("STALE_AFTER_HOURS", "72"))
    refresh_interval_hours: int = int(os.getenv("REFRESH_INTERVAL_HOURS", "12"))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()

# ---- Documented scoring weights (see README "Matching methodology") ----
ROLE_WEIGHTS = {"core_skills": 0.45, "preferred_skills": 0.15, "evidence": 0.15, "semantic": 0.25}
MATCH_WEIGHTS = {"skills": 0.40, "semantic": 0.30, "role_alignment": 0.15, "eligibility": 0.15}

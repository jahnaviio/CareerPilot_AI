"""
Centralized configuration for CareerPilot AI.

Every environment-dependent value lives here so the rest of the codebase
never reads os.environ directly. This makes the app portable across
local dev, Streamlit Community Cloud, and self-hosted deployments.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "careerpilot.db"
SEED_INTERNSHIPS_CSV = DATA_DIR / "seed_internships.csv"


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LLMConfig:
    """
    Pluggable LLM provider settings.

    PROVIDER = "claude"  -> uses Anthropic API (ANTHROPIC_API_KEY required)
    PROVIDER = "ollama"  -> uses a local Ollama server (no API key, needs
                            `ollama serve` running locally)
    PROVIDER = "none"    -> disables AI text generation; app falls back to
                            rule-based / template output everywhere so it
                            still works with zero external dependencies.
    """
    provider: str = os.getenv("LLM_PROVIDER", "claude").strip().lower()

    # Claude API
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "2000"))

    # Ollama
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")

    @property
    def is_configured(self) -> bool:
        if self.provider == "claude":
            return bool(self.anthropic_api_key)
        if self.provider == "ollama":
            return True  # assume reachable; agent calls handle failure
        return False  # "none" or unrecognized


@dataclass(frozen=True)
class JobIngestionConfig:
    """Settings for the real internship discovery pipeline."""
    remotive_api_url: str = "https://remotive.com/api/remote-jobs"
    keywords: tuple = (
        "intern", "internship", "ai", "machine learning", "ml",
        "data", "python", "genai", "nlp",
    )
    max_jobs_per_fetch: int = int(os.getenv("MAX_JOBS_PER_FETCH", "50"))
    request_timeout_seconds: int = int(os.getenv("JOB_FETCH_TIMEOUT", "10"))


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "CareerPilot AI"
    default_user_id: int = 1  # single-user mode for v1; see core/models.py note
    high_match_threshold: int = int(os.getenv("HIGH_MATCH_THRESHOLD", "70"))
    debug: bool = _env_bool("DEBUG", False)


llm_config = LLMConfig()
job_config = JobIngestionConfig()
app_config = AppConfig()

"""Test environment: isolated DB/data dirs, hashing embedder (no model download), no LLM unless a test injects a fake."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cp_tests_"))
os.environ.update({"DATABASE_URL": f"sqlite:///{_TMP / 'ui.db'}", "DATA_DIR": str(_TMP), "CHROMA_DIR": str(_TMP / "chroma"),
                   "EMBEDDING_BACKEND": "hashing", "LLM_PROVIDER": "none", "APP_ENV": "development", "HTTP_MIN_INTERVAL_SECONDS": "0"})

import pytest  # noqa: E402

from core.db import init_db_for_dev, make_session_factory, get_engine  # noqa: E402
from ml.embeddings import HashingEmbedder  # noqa: E402
from rag.store import VectorStore  # noqa: E402
from services.workflow import CareerPilot  # noqa: E402
from tests.helpers import FakeLLM  # noqa: E402


@pytest.fixture()
def factory(tmp_path):
    eng = get_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db_for_dev(eng)
    return make_session_factory(eng)


@pytest.fixture()
def embedder():
    return HashingEmbedder()


@pytest.fixture()
def app(factory, embedder):
    return CareerPilot(factory, embedder=embedder, store=VectorStore(embedder, force_memory=True), llm=None)


@pytest.fixture()
def app_llm(factory, embedder):
    llm = FakeLLM()
    a = CareerPilot(factory, embedder=embedder, store=VectorStore(embedder, force_memory=True), llm=llm)
    a.fake = llm
    return a

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ai.embeddings import HashingEmbedder  # noqa: E402
from backend.ai.retrieval import HybridRetriever, load_chunks  # noqa: E402
from backend.ai.workflow import InvestigationPipeline  # noqa: E402
from backend.config import get_settings  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return dataclasses.replace(
        get_settings(),
        storage="memory",
        openai_api_key="",
        redis_url="",
        api_key="",
        runbooks_dir=str(ROOT / "runbooks"),
        rate_limit_per_minute=0,
    )


@pytest.fixture(scope="session")
def retriever(settings):
    return HybridRetriever(load_chunks(settings.runbooks_dir), HashingEmbedder())


@pytest.fixture()
def pipeline(retriever, settings):
    return InvestigationPipeline(retriever, settings, llm=None)


DB_LOGS = (
    "2026-11-15 10:00:02 ERROR Database connection timeout after 30s\n"
    "2026-11-15 10:00:03 ERROR too many connections for role payments\n"
    "2026-11-15 10:00:04 ERROR Database connection timeout after 30s\n"
)

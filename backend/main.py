"""FastAPI entry point.  Run:  uvicorn backend.main:app"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.ai.embeddings import make_embedder
from backend.ai.llm import make_llm
from backend.ai.retrieval import HybridRetriever, load_chunks
from backend.ai.workflow import InvestigationPipeline
from backend.api.routes import public, router
from backend.config import get_settings
from backend.db.memory import MemoryRepository
from backend.deps import AppContext
from backend.infra.cache import Cache

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("opspilot")


def build_context(settings=None) -> AppContext:
    settings = settings or get_settings()

    if settings.storage == "memory":
        repo = MemoryRepository()
    else:
        from backend.db.postgres import PostgresRepository

        repo = PostgresRepository(settings.database_url)
    repo.open()

    chunks = load_chunks(settings.runbooks_dir)
    if not chunks:
        logger.warning("No runbooks found in %s", settings.runbooks_dir)
    retriever = HybridRetriever(chunks, make_embedder(settings), settings.index_cache_dir)

    pipeline = InvestigationPipeline(retriever, settings, make_llm(settings))
    logger.info(
        "ready: storage=%s ai_mode=%s embedder=%s chunks=%d",
        repo.name,
        pipeline.mode,
        retriever.embedder.name,
        retriever.size,
    )
    return AppContext(settings, repo, Cache(settings.redis_url), retriever, pipeline)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Heavy objects (DB pool, index, compiled graph) are built once here.
    app.state.ctx = build_context()
    try:
        yield
    finally:
        app.state.ctx.repo.close()


app = FastAPI(title="OpsPilot AI", version="1.0.0", lifespan=lifespan)
app.include_router(public)
app.include_router(router)

"""Application settings, read from environment variables (and .env)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Storage: "postgres" (real) or "memory" (demo/tests, data lost on restart)
    storage: str
    database_url: str
    redis_url: str

    # AI. Without OPENAI_API_KEY the app still works in offline mode
    # (hashing embeddings + rule-based RCA), clearly marked in results.
    openai_api_key: str
    openai_model: str
    embedding_model: str

    runbooks_dir: str
    index_cache_dir: str

    # Security: if API_KEY is set, every request must send X-API-Key.
    api_key: str

    max_rca_attempts: int
    rate_limit_per_minute: int
    max_log_chars: int


def get_settings() -> Settings:
    return Settings(
        storage=os.getenv("STORAGE", "postgres").lower(),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        runbooks_dir=os.getenv("RUNBOOKS_DIR", "runbooks"),
        index_cache_dir=os.getenv("INDEX_CACHE_DIR", ".cache/index"),
        api_key=os.getenv("API_KEY", ""),
        max_rca_attempts=max(1, _int("MAX_RCA_ATTEMPTS", 3)),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 10),
        max_log_chars=_int("MAX_LOG_CHARS", 8000),
    )

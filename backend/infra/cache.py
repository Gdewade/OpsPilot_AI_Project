"""Optional Redis cache and rate limiter.

Redis is an optimisation, never a requirement: if it is missing or goes
down, reads become cache misses and rate limiting falls back to an
in-process counter. The API keeps working.
"""

import json
import logging
import threading
import time

logger = logging.getLogger("opspilot.cache")


class Cache:
    def __init__(self, redis_url: str = ""):
        self._client = None
        self._lock = threading.Lock()
        self._local_hits: dict[str, tuple[int, float]] = {}
        if redis_url:
            try:
                import redis

                self._client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            except Exception as exc:  # missing package or bad URL
                logger.warning("Redis disabled: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get_json(self, key: str):
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("cache get failed: %s", exc)
            return None

    def set_json(self, key: str, value, ttl: int = 300):
        if not self._client:
            return
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("cache set failed: %s", exc)

    def delete(self, key: str):
        if not self._client:
            return
        try:
            self._client.delete(key)
        except Exception as exc:
            logger.warning("cache delete failed: %s", exc)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Fixed-window rate limit. limit <= 0 disables limiting."""
        if limit <= 0:
            return True
        if self._client:
            try:
                bucket = f"rl:{key}:{int(time.time() // window_seconds)}"
                count = self._client.incr(bucket)
                if count == 1:
                    self._client.expire(bucket, window_seconds)
                return count <= limit
            except Exception as exc:
                logger.warning("rate limiter fell back to local: %s", exc)
        return self._allow_local(key, limit, window_seconds)

    def _allow_local(self, key, limit, window_seconds):
        now = time.time()
        with self._lock:
            count, started = self._local_hits.get(key, (0, now))
            if now - started >= window_seconds:
                count, started = 0, now
            count += 1
            self._local_hits[key] = (count, started)
            return count <= limit

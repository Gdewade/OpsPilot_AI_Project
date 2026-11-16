"""Shared application objects and the API-key dependency."""

import hmac
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, Request


@dataclass
class AppContext:
    settings: Any
    repo: Any
    cache: Any
    retriever: Any
    pipeline: Any


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)):
    """If API_KEY is configured, every protected route needs a matching X-API-Key."""
    expected = request.app.state.ctx.settings.api_key
    if not expected:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

"""Thin HTTP client for the OpsPilot API."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def call(method: str, path: str, timeout: int = 30, **kwargs):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    try:
        resp = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(0, f"Cannot reach the API at {API_URL}: {exc.__class__.__name__}") from exc
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(resp.status_code, str(detail))
    return resp.json()


def get(path, **kw):
    return call("GET", path, **kw)


def post(path, **kw):
    return call("POST", path, **kw)


def patch(path, **kw):
    return call("PATCH", path, **kw)

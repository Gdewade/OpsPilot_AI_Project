"""Embedding back-ends.

OpenAIEmbedder gives real semantic vectors. HashingEmbedder is an offline
fallback (hashed word and bigram features): deterministic and free, but it
only matches shared words, not meaning. Results are labelled with the
embedder name so the difference is never hidden.
"""

import re
import zlib

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class HashingEmbedder:
    def __init__(self, dim: int = 512):
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = tokenize(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feat in features:
            h = zlib.crc32(feat.encode())
            vec[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._embed(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str):
        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(model=model, api_key=api_key)
        self.name = f"openai-{model}"

    @staticmethod
    def _norm(arr: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(arr, axis=-1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._norm(np.array(self._client.embed_documents(texts), dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        return self._norm(np.array(self._client.embed_query(text), dtype=np.float32))


def make_embedder(settings):
    """OpenAI if a key is configured and works, otherwise the offline one."""
    if settings.openai_api_key:
        try:
            return OpenAIEmbedder(settings.openai_api_key, settings.embedding_model)
        except Exception:  # package missing or bad config
            import logging

            logging.getLogger("opspilot.ai").warning(
                "OpenAI embeddings unavailable, using offline hashing embedder",
                exc_info=True,
            )
    return HashingEmbedder()

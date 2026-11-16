"""Hybrid runbook retrieval: BM25 + vector similarity, fused with RRF.

- Runbooks are chunked by markdown heading ("## Symptoms", "## Remediation"...)
  so a chunk is one meaningful section, not an arbitrary 500 characters.
- BM25 is implemented here with numpy (no extra dependency).
- Document embeddings are cached on disk, so a restart does not re-embed.
"""

import hashlib
import logging
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from backend.ai.embeddings import tokenize

logger = logging.getLogger("opspilot.retrieval")

_STOPWORDS = frozenset(
    "a an and are as at be by for from in is it of on or that the this to was with".split()
)


def _terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in _STOPWORDS]


def load_chunks(runbooks_dir: str) -> list[dict]:
    """Split every .md file in the folder into one chunk per '## ' section."""
    chunks = []
    for path in sorted(Path(runbooks_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", text, re.M)
        title = title_match.group(1).strip() if title_match else path.stem
        parts = re.split(r"^##\s+", text, flags=re.M)
        for part in parts[1:]:
            heading, _, body = part.partition("\n")
            body = body.strip()
            if not body:
                continue
            chunks.append(
                {
                    "source": path.name,
                    "title": title,
                    "section": heading.strip(),
                    "content": f"{title} - {heading.strip()}\n{body}",
                }
            )
    return chunks


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df = Counter(t for d in self.tf for t in d)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query_terms: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tf), dtype=np.float32)
        for i, tf in enumerate(self.tf):
            norm = self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1.0))
            for term in set(query_terms):
                f = tf.get(term, 0)
                if f:
                    out[i] += self.idf.get(term, 0.0) * f * (self.k1 + 1) / (f + norm)
        return out


class HybridRetriever:
    def __init__(self, chunks: list[dict], embedder, cache_dir: str | None = None):
        self.chunks = chunks
        self.embedder = embedder
        self.bm25 = BM25([_terms(c["content"]) for c in chunks])
        self.vectors = self._load_vectors(cache_dir)

    @property
    def size(self) -> int:
        return len(self.chunks)

    def _load_vectors(self, cache_dir):
        texts = [c["content"] for c in self.chunks]
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        digest = hashlib.sha256("\n".join(texts).encode()).hexdigest()[:16]
        cache_file = None
        if cache_dir:
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", self.embedder.name)
            cache_file = Path(cache_dir) / f"{safe}-{digest}.npy"
            try:
                if cache_file.exists():
                    return np.load(cache_file)
            except Exception:
                logger.warning("could not read index cache", exc_info=True)
        vectors = self.embedder.embed_documents(texts)
        if cache_file:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                np.save(cache_file, vectors)
            except Exception:
                logger.warning("could not write index cache", exc_info=True)
        return vectors

    def search(self, query: str, k: int = 3, pool: int = 10) -> list[dict]:
        """Return the top-k chunks, best first, each with an RRF score."""
        if not self.chunks or not query.strip():
            return []
        bm25_scores = self.bm25.scores(_terms(query))
        vec_scores = self.vectors @ self.embedder.embed_query(query)

        def ranking(scores: np.ndarray, require_positive: bool) -> list[int]:
            order = np.argsort(-scores)[:pool]
            return [int(i) for i in order if not require_positive or scores[i] > 0]

        fused: dict[int, float] = {}
        for ranked in (ranking(bm25_scores, True), ranking(vec_scores, False)):
            for rank, idx in enumerate(ranked, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (60 + rank)

        top = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [
            {**self.chunks[i], "score": round(score, 5), "rank": n}
            for n, (i, score) in enumerate(top, start=1)
        ]

    def with_remediation(self, results: list[dict], max_sources: int = 2) -> list[dict]:
        """Make sure the Remediation section of the best-matching runbooks is
        included, even if another section of that runbook ranked higher.
        Without this the answer could name a cause but have no fix."""
        out = list(results)
        have = {(r["source"], r["section"]) for r in out}
        best_sources = []
        for r in results:
            if r["source"] not in best_sources:
                best_sources.append(r["source"])
        for source in best_sources[:max_sources]:
            for chunk in self.chunks:
                key = (chunk["source"], chunk["section"])
                if chunk["source"] == source and chunk["section"].lower().startswith("remediation") and key not in have:
                    out.append({**chunk, "score": 0.0, "rank": len(out) + 1, "added": "remediation"})
                    have.add(key)
        return out

    def sources(self) -> list[str]:
        return sorted({c["source"] for c in self.chunks})

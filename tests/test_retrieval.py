import numpy as np

from backend.ai.embeddings import HashingEmbedder
from backend.ai.retrieval import BM25, HybridRetriever, load_chunks


def test_chunks_follow_markdown_headings(settings):
    chunks = load_chunks(settings.runbooks_dir)
    assert len(chunks) > 20
    sections = {c["section"] for c in chunks}
    assert {"Symptoms", "Remediation"} <= sections
    assert all(c["content"].startswith(c["title"]) for c in chunks)


def test_bm25_ranks_matching_document_first():
    bm = BM25([["database", "timeout"], ["disk", "full"], ["cpu", "high"]])
    scores = bm.scores(["disk"])
    assert int(np.argmax(scores)) == 1
    assert scores[0] == 0 and scores[2] == 0


def test_search_finds_right_runbook(retriever):
    top = retriever.search("redis connection refused cache", k=3)
    assert top[0]["source"] == "redis_connection_failure.md"
    assert [r["rank"] for r in top] == [1, 2, 3]


def test_empty_query_returns_nothing(retriever):
    assert retriever.search("   ") == []


def test_with_remediation_adds_the_fix_section(retriever):
    results = retriever.search("database connection timeout", k=1)
    expanded = retriever.with_remediation(results)
    assert any(r["section"].lower().startswith("remediation") for r in expanded)


def test_index_cache_is_reused(tmp_path, settings):
    chunks = load_chunks(settings.runbooks_dir)
    HybridRetriever(chunks, HashingEmbedder(), cache_dir=str(tmp_path))
    files = list(tmp_path.glob("*.npy"))
    assert len(files) == 1

    class Boom(HashingEmbedder):
        def embed_documents(self, texts):  # must not be called on the second build
            raise AssertionError("documents were re-embedded")

    HybridRetriever(chunks, Boom(), cache_dir=str(tmp_path))

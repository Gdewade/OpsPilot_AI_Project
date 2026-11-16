"""Measure retrieval and root-cause quality on a labelled incident set.

Usage:  python -m eval.run_eval

Works offline (hashing embeddings + rule-based RCA). With OPENAI_API_KEY set
it uses OpenAI embeddings and the LLM, so you can compare both modes.

Cases with "expected": null are unknown incidents: the right behaviour is
to escalate to a human, not to guess.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ai.embeddings import make_embedder  # noqa: E402
from backend.ai.llm import make_llm  # noqa: E402
from backend.ai.retrieval import HybridRetriever, load_chunks  # noqa: E402
from backend.ai.workflow import InvestigationPipeline, build_query  # noqa: E402
from backend.analysis.log_analyzer import analyze_logs  # noqa: E402
from backend.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    retriever = HybridRetriever(
        load_chunks(str(ROOT / settings.runbooks_dir)), make_embedder(settings), settings.index_cache_dir
    )
    pipeline = InvestigationPipeline(retriever, settings, make_llm(settings))
    cases = [json.loads(line) for line in (ROOT / "eval/cases.jsonl").read_text().splitlines() if line.strip()]

    known = [c for c in cases if c["expected"]]
    unknown = [c for c in cases if not c["expected"]]
    top1 = top3 = rca_ok = 0
    rows = []

    for c in known:
        analysis = analyze_logs(c["logs"])
        query = build_query({"title": c["title"], "analysis": analysis, "attempt": 0})
        ranked_sources = []
        for r in retriever.search(query, k=6):
            if r["source"] not in ranked_sources:
                ranked_sources.append(r["source"])
        top1 += ranked_sources[:1] == [c["expected"]]
        top3 += c["expected"] in ranked_sources[:3]

        state = pipeline.run_sequential({"title": c["title"], "log_text": c["logs"]})
        ok = state["status"] == "completed" and c["expected"] in state["rca"]["cited_runbooks"]
        rca_ok += ok
        rows.append((c["title"], c["expected"], ranked_sources[:1], state["status"], ok))

    escalated = 0
    for c in unknown:
        state = pipeline.run_sequential({"title": c["title"], "log_text": c["logs"]})
        escalated += state["status"] == "needs_human"

    n = len(known)
    print(f"mode: {pipeline.mode} | embedder: {retriever.embedder.name} | known={n} unknown={len(unknown)}\n")
    for title, expected, got, status, ok in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {title:36} expected={expected:34} top1={got[0] if got else '-':34} {status}")
    print(f"\nRetrieval top-1 accuracy : {top1}/{n} = {top1 / n:.0%}")
    print(f"Retrieval top-3 hit rate : {top3}/{n} = {top3 / n:.0%}")
    print(f"End-to-end RCA correct   : {rca_ok}/{n} = {rca_ok / n:.0%}")
    if unknown:
        print(f"Unknown incidents escalated to a human: {escalated}/{len(unknown)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

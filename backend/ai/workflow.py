"""Investigation workflow (LangGraph).

    analyze -> retrieve -> rca -> verify --sufficient--> finalize -> END
                  ^                 |
                  |                 +--weak, attempts left--> rewrite_query
                  +-------------------------------------------------+
                                    |
                                    +--weak, out of attempts--> escalate -> END

If the evidence stays weak after the allowed attempts, the investigation
ends as "needs_human" instead of presenting a guess as a conclusion.

The nodes are plain methods. `run_sequential` walks the same nodes and the
same routing function without LangGraph (used in tests and as a fallback).
"""

import logging
import re
from typing import TypedDict

from backend.ai.llm import generate_rca
from backend.ai.verification import verify_rca
from backend.analysis.log_analyzer import analyze_logs

logger = logging.getLogger("opspilot.workflow")


class InvestigationState(TypedDict, total=False):
    title: str
    log_text: str
    analysis: dict
    attempt: int
    query: str
    runbooks: list
    rca: dict
    verification: dict
    status: str
    trace: list


def _dedupe_words(text: str, limit: int = 40) -> str:
    words, seen = [], set()
    for w in re.findall(r"[A-Za-z0-9_]+", text):
        lw = w.lower()
        if lw not in seen and len(lw) > 2:
            seen.add(lw)
            words.append(w)
    return " ".join(words[:limit])


def build_query(state: InvestigationState) -> str:
    """Each retry uses a different strategy so we do not repeat the same search."""
    analysis, title, attempt = state["analysis"], state["title"], state.get("attempt", 0)
    errors = analysis["unique_errors"][:5]
    if attempt == 0:
        return f"{title}\n" + "\n".join(errors)
    if attempt == 1:
        return _dedupe_words(" ".join(errors + analysis["unique_warnings"][:3]))
    return " ".join(analysis["signals"]) + " " + _dedupe_words(title + " " + " ".join(errors[:2]), 15)


class InvestigationPipeline:
    def __init__(self, retriever, settings, llm=None):
        self.retriever = retriever
        self.settings = settings
        self.llm = llm
        self._graph = None

    @property
    def mode(self) -> str:
        return "llm" if self.llm is not None else "offline"

    # ---- nodes -------------------------------------------------------
    def analyze(self, state):
        analysis = analyze_logs(state["log_text"])
        note = f"analyze: severity={analysis['severity']}, errors={analysis['error_count']}"
        if analysis["injection_suspected"]:
            note += " (possible prompt injection in logs; treated as data)"
        return {"analysis": analysis, "attempt": 0, "trace": [note]}

    def retrieve(self, state):
        query = build_query(state)
        k = 3 + state.get("attempt", 0)
        results = self.retriever.with_remediation(self.retriever.search(query, k=k))
        note = f"retrieve (attempt {state.get('attempt', 0) + 1}): {len(results)} chunks"
        return {"query": query, "runbooks": results, "trace": state["trace"] + [note]}

    def rca(self, state):
        result = generate_rca(
            state["title"], state["log_text"], state["analysis"], state["runbooks"], self.settings, self.llm
        )
        return {"rca": result.model_dump(), "trace": state["trace"] + [f"rca: mode={result.mode}"]}

    def verify(self, state):
        v = verify_rca(state["rca"], state["log_text"], state["runbooks"])
        note = f"verify: score={v['score']} sufficient={v['sufficient']}"
        return {"verification": v, "trace": state["trace"] + [note]}

    def rewrite(self, state):
        attempt = state.get("attempt", 0) + 1
        return {"attempt": attempt, "trace": state["trace"] + [f"rewrite: trying query strategy {attempt}"]}

    def finalize(self, state):
        return {"status": "completed", "trace": state["trace"] + ["done: evidence verified"]}

    def escalate(self, state):
        return {
            "status": "needs_human",
            "trace": state["trace"] + ["escalate: evidence stayed weak, a human must review"],
        }

    # ---- routing -----------------------------------------------------
    def route(self, state) -> str:
        if state["verification"]["sufficient"]:
            return "done"
        if state.get("attempt", 0) + 1 < self.settings.max_rca_attempts:
            return "retry"
        return "escalate"

    # ---- execution ---------------------------------------------------
    def build_graph(self):
        from langgraph.graph import END, START, StateGraph

        g = StateGraph(InvestigationState)
        for name in ("analyze", "retrieve", "rca", "verify", "rewrite", "finalize", "escalate"):
            g.add_node(name, getattr(self, name))
        g.add_edge(START, "analyze")
        g.add_edge("analyze", "retrieve")
        g.add_edge("retrieve", "rca")
        g.add_edge("rca", "verify")
        g.add_conditional_edges(
            "verify", self.route, {"done": "finalize", "retry": "rewrite", "escalate": "escalate"}
        )
        g.add_edge("rewrite", "retrieve")
        g.add_edge("finalize", END)
        g.add_edge("escalate", END)
        return g.compile()

    def run_sequential(self, state: InvestigationState) -> InvestigationState:
        state = {**state, **self.analyze(state)}
        while True:
            state.update(self.retrieve(state))
            state.update(self.rca(state))
            state.update(self.verify(state))
            decision = self.route(state)
            if decision == "retry":
                state.update(self.rewrite(state))
                continue
            state.update(self.finalize(state) if decision == "done" else self.escalate(state))
            return state

    def run(self, title: str, log_text: str) -> InvestigationState:
        initial: InvestigationState = {"title": title, "log_text": log_text}
        try:
            if self._graph is None:
                self._graph = self.build_graph()
            return self._graph.invoke(initial)
        except ImportError:
            logger.warning("langgraph not installed, running the same steps sequentially")
            return self.run_sequential(initial)

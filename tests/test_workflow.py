import dataclasses

import pytest

from backend.ai.llm import RCAResult, generate_rca
from backend.ai.workflow import InvestigationPipeline, build_query
from backend.analysis.log_analyzer import analyze_logs
from tests.conftest import DB_LOGS


def test_known_incident_completes_with_verified_fix(pipeline):
    st = pipeline.run_sequential({"title": "Payments failing", "log_text": DB_LOGS})
    assert st["status"] == "completed"
    assert st["rca"]["cited_runbooks"] == ["database_connection_timeout.md"]
    assert st["rca"]["remediation_steps"]
    assert st["verification"]["sufficient"]
    assert st["attempt"] == 0


def test_unrelated_logs_retry_then_escalate_to_human(pipeline):
    st = pipeline.run_sequential({"title": "Odd thing", "log_text": "ERROR xyzzy plugh frobnicate\nERROR zork blorb"})
    assert st["status"] == "needs_human"
    assert st["attempt"] + 1 == pipeline.settings.max_rca_attempts
    assert sum(t.startswith("retrieve") for t in st["trace"]) == 3
    assert not st["verification"]["sufficient"]


def test_max_attempts_is_respected(retriever, settings):
    p = InvestigationPipeline(retriever, dataclasses.replace(settings, max_rca_attempts=1), None)
    st = p.run_sequential({"title": "x", "log_text": "ERROR xyzzy plugh"})
    assert st["status"] == "needs_human" and st["attempt"] == 0


def test_each_retry_uses_a_different_query():
    analysis = analyze_logs("ERROR Database connection timeout\nWARNING slow response")
    base = {"title": "Payments", "analysis": analysis}
    queries = {build_query({**base, "attempt": i}) for i in range(3)}
    assert len(queries) == 3


def test_llm_answer_with_invented_log_line_is_rejected(retriever, settings):
    class LyingLLM:
        def invoke(self, messages):
            return RCAResult(
                root_cause="The sun flared.", confidence=0.95,
                supporting_log_lines=["ERROR solar flare detected"],
                cited_runbooks=["database_connection_timeout.md"],
                remediation_steps=["Wait"],
            )

    p = InvestigationPipeline(retriever, settings, llm=LyingLLM())
    st = p.run_sequential({"title": "Payments failing", "log_text": DB_LOGS})
    assert st["status"] == "needs_human"
    assert st["verification"]["fabricated_log_lines"]


def test_good_llm_answer_is_accepted(retriever, settings):
    class GoodLLM:
        def invoke(self, messages):
            return RCAResult(
                root_cause="DB connections exhausted.", confidence=0.9,
                supporting_log_lines=["ERROR too many connections for role payments"],
                cited_runbooks=["database_connection_timeout.md"],
                remediation_steps=["Raise max_connections"],
            )

    p = InvestigationPipeline(retriever, settings, llm=GoodLLM())
    st = p.run_sequential({"title": "Payments failing", "log_text": DB_LOGS})
    assert st["status"] == "completed" and st["rca"]["mode"] == "llm"


def test_llm_failure_falls_back_to_offline_analysis(retriever, settings):
    class Broken:
        def invoke(self, messages):
            raise RuntimeError("API down")

    analysis = analyze_logs(DB_LOGS)
    result = generate_rca("t", DB_LOGS, analysis, retriever.search("database timeout"), settings, llm=Broken())
    assert result.mode == "heuristic_fallback"


def test_langgraph_matches_sequential_run(pipeline):
    pytest.importorskip("langgraph")
    initial = {"title": "Payments failing", "log_text": DB_LOGS}
    graph_state = pipeline.run(**initial)
    seq_state = pipeline.run_sequential(initial)
    assert graph_state["status"] == seq_state["status"]
    assert graph_state["rca"]["cited_runbooks"] == seq_state["rca"]["cited_runbooks"]

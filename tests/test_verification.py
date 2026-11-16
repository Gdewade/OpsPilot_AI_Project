from backend.ai.verification import verify_rca

LOGS = "2026-11-15 10:00:02 ERROR Database connection timeout after 30s\nINFO ok"
RUNBOOKS = [
    {"source": "database_connection_timeout.md", "section": "Symptoms",
     "content": "Database Connection Timeout - Symptoms\nlogs show database connection timeout"},
]


def rca(**over):
    base = {
        "supporting_log_lines": ["ERROR Database connection timeout after 30s"],
        "cited_runbooks": ["database_connection_timeout.md"],
        "confidence": 0.8,
    }
    return {**base, **over}


def test_valid_answer_passes():
    v = verify_rca(rca(), LOGS, RUNBOOKS)
    assert v["sufficient"] and v["issues"] == []
    assert "database" in v["grounded_terms"]


def test_fabricated_log_line_is_caught():
    v = verify_rca(rca(supporting_log_lines=["ERROR the moon exploded"]), LOGS, RUNBOOKS)
    assert not v["sufficient"]
    assert v["fabricated_log_lines"] == ["ERROR the moon exploded"]


def test_citing_a_runbook_that_was_not_retrieved_is_caught():
    v = verify_rca(rca(cited_runbooks=["made_up.md"]), LOGS, RUNBOOKS)
    assert not v["sufficient"]
    assert v["invalid_runbooks"] == ["made_up.md"]


def test_low_confidence_is_insufficient():
    assert not verify_rca(rca(confidence=0.1), LOGS, RUNBOOKS)["sufficient"]


def test_real_line_but_unrelated_runbook_is_not_grounded():
    unrelated = [{"source": "disk_space_full.md", "section": "Symptoms", "content": "Disk Space Full\nno space left"}]
    v = verify_rca(rca(cited_runbooks=["disk_space_full.md"]), LOGS, unrelated)
    assert not v["sufficient"]
    assert v["grounded_terms"] == []


def test_line_match_ignores_timestamp_and_case():
    v = verify_rca(rca(supporting_log_lines=["error database CONNECTION timeout after 30s"]), LOGS, RUNBOOKS)
    assert v["verified_log_lines"]


def test_one_real_and_one_invented_line_is_still_rejected():
    """A mostly-correct answer must not pass if it also invents evidence."""
    v = verify_rca(
        rca(supporting_log_lines=[
            "ERROR Database connection timeout after 30s",  # real
            "ERROR replica lag exceeded 900s",              # invented
        ]),
        LOGS,
        RUNBOOKS,
    )
    assert v["verified_log_lines"] and v["fabricated_log_lines"]
    assert not v["sufficient"]

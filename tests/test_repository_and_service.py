import pytest

from backend.db.memory import MemoryRepository
from backend.infra.cache import Cache
from backend.services.investigation_service import run_investigation
from tests.conftest import DB_LOGS


@pytest.fixture()
def repo():
    return MemoryRepository()


def make_incident(repo, logs=DB_LOGS):
    return repo.create_incident("Payments failing", "payments return 500", logs, "high", "tester")


def test_incident_filters_and_pagination(repo):
    for _ in range(3):
        make_incident(repo)
    repo.update_status(1, "resolved")
    items, total = repo.list_incidents(status="open")
    assert total == 2 and all(i["status"] == "open" for i in items)
    page, total = repo.list_incidents(limit=1, offset=1)
    assert total == 3 and len(page) == 1


def test_approval_can_only_be_decided_once(repo):
    make_incident(repo)
    ap = repo.create_approval(1, "restart db", "bot")
    assert repo.decide_approval(ap["id"], "approved", "alice", "ok")["decision"] == "approved"
    assert repo.decide_approval(ap["id"], "rejected", "bob", "late") is None
    assert repo.get_approval(ap["id"])["reviewed_by"] == "alice"


def test_investigation_creates_approval_and_audit_trail(repo, pipeline):
    make_incident(repo)
    out = run_investigation(repo, Cache(), pipeline, 1, "tester")
    assert out["status"] == "completed" and out["approval_id"]
    assert repo.get_approval(out["approval_id"])["decision"] == "pending"
    actions = [a["action"] for a in repo.list_audit(1)]
    for expected in ("INVESTIGATION_STARTED", "APPROVAL_REQUESTED", "INVESTIGATION_COMPLETED"):
        assert expected in actions
    assert repo.latest_investigation(1)["result"]["rca"]["remediation_steps"]


def test_weak_evidence_escalates_and_requests_no_approval(repo, pipeline):
    make_incident(repo, "ERROR xyzzy plugh frobnicate")
    out = run_investigation(repo, Cache(), pipeline, 1, "tester")
    assert out["status"] == "needs_human" and out["approval_id"] is None
    assert repo.get_incident(1)["status"] == "needs_human"
    assert "INVESTIGATION_ESCALATED" in [a["action"] for a in repo.list_audit(1)]


def test_failed_investigation_restores_status(repo, pipeline, monkeypatch):
    make_incident(repo)
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        run_investigation(repo, Cache(), pipeline, 1, "tester")
    assert repo.get_incident(1)["status"] == "open"
    assert "INVESTIGATION_FAILED" in [a["action"] for a in repo.list_audit(1)]


def test_unknown_incident_raises(repo, pipeline):
    with pytest.raises(LookupError):
        run_investigation(repo, Cache(), pipeline, 99, "tester")


def test_rate_limiter_blocks_after_limit_and_works_without_redis():
    cache = Cache("")
    assert [cache.allow("k", 2) for _ in range(3)] == [True, True, False]
    assert cache.allow("k", 0) is True  # 0 disables limiting


# ---- what an approval decision does to the incident status -------------
from backend.services.approval_service import apply_decision_outcome, status_after_decision  # noqa: E402


def test_status_rules():
    assert status_after_decision("investigating", "approved", 0) == "resolved"
    assert status_after_decision("investigating", "approved", 1) is None  # another request still waiting
    assert status_after_decision("investigating", "rejected", 0) == "needs_human"
    for other in ("open", "resolved", "needs_human"):
        assert status_after_decision(other, "approved", 0) is None
        assert status_after_decision(other, "rejected", 0) is None


def _investigated(repo, pipeline):
    make_incident(repo)
    return run_investigation(repo, Cache(), pipeline, 1, "tester")


def test_approving_the_fix_resolves_the_incident_and_is_audited(repo, pipeline):
    out = _investigated(repo, pipeline)
    ap = repo.get_approval(out["approval_id"])
    repo.decide_approval(ap["id"], "approved", "alice", "ok")
    assert apply_decision_outcome(repo, Cache(), ap, "approved", "alice") == "resolved"
    assert repo.get_incident(1)["status"] == "resolved"
    assert "STATUS_CHANGED" in [a["action"] for a in repo.list_audit(1)]


def test_rejecting_the_fix_sends_the_incident_to_a_human(repo, pipeline):
    out = _investigated(repo, pipeline)
    ap = repo.get_approval(out["approval_id"])
    repo.decide_approval(ap["id"], "rejected", "alice", "not safe")
    assert apply_decision_outcome(repo, Cache(), ap, "rejected", "alice") == "needs_human"
    assert repo.get_incident(1)["status"] == "needs_human"


def test_incident_stays_open_while_another_request_is_pending(repo, pipeline):
    out = _investigated(repo, pipeline)
    repo.create_approval(1, "second action", "bob")  # still pending
    ap = repo.get_approval(out["approval_id"])
    repo.decide_approval(ap["id"], "approved", "alice", None)
    assert apply_decision_outcome(repo, Cache(), ap, "approved", "alice") is None
    assert repo.get_incident(1)["status"] == "investigating"

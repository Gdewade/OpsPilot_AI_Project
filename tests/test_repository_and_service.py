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

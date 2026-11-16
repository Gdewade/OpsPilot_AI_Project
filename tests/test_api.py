"""API tests. Skipped automatically if FastAPI is not installed."""

import dataclasses

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app, build_context  # noqa: E402
from tests.conftest import DB_LOGS  # noqa: E402


@pytest.fixture()
def client(settings):
    app.state.ctx = build_context(settings)
    # TestClient without a `with` block skips lifespan; we set the context ourselves.
    return TestClient(app)


def new_incident(client, logs=DB_LOGS):
    r = client.post("/incidents", json={"title": "Payments failing", "description": "returns 500", "log_text": logs, "created_by": "tester"})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_is_public_and_reports_mode(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["ai_mode"] == "offline"


def test_severity_derived_from_logs(client):
    assert new_incident(client)["severity"] == "high"


def test_validation_rejects_bad_input(client):
    assert client.post("/incidents", json={"title": "x"}).status_code == 422
    assert client.get("/incidents", params={"status": "bogus"}).status_code == 422
    inc = new_incident(client)
    r = client.patch(f"/incidents/{inc['id']}/status", json={"status": "bogus", "changed_by": "me"})
    assert r.status_code == 422


def test_missing_incident_is_404(client):
    assert client.get("/incidents/999").status_code == 404


def test_full_flow_investigate_then_approve(client):
    inc = new_incident(client)
    out = client.post(f"/incidents/{inc['id']}/investigate", json={"requested_by": "tester"}).json()
    assert out["status"] == "completed" and out["approval_id"]

    ap = client.post(f"/approvals/{out['approval_id']}/decision",
                     json={"decision": "approved", "reviewed_by": "alice", "comments": "go"})
    assert ap.status_code == 200 and ap.json()["decision"] == "approved"
    again = client.post(f"/approvals/{out['approval_id']}/decision",
                        json={"decision": "rejected", "reviewed_by": "bob"})
    assert again.status_code == 409

    actions = [a["action"] for a in client.get(f"/incidents/{inc['id']}/audit").json()["audit_logs"]]
    assert "APPROVAL_APPROVED" in actions and "INCIDENT_CREATED" in actions


def test_requester_cannot_approve_own_request(client):
    inc = new_incident(client)
    ap = client.post("/approvals", json={"incident_id": inc["id"], "action": "restart db", "requested_by": "alice"}).json()
    r = client.post(f"/approvals/{ap['id']}/decision", json={"decision": "approved", "reviewed_by": "alice"})
    assert r.status_code == 403


def test_api_key_is_enforced_when_configured(settings):
    secured = dataclasses.replace(settings, api_key="s3cret")
    app.state.ctx = build_context(secured)
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.get("/incidents").status_code == 401
    assert c.get("/incidents", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/incidents", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_investigation_rate_limit(settings):
    limited = dataclasses.replace(settings, rate_limit_per_minute=1)
    app.state.ctx = build_context(limited)
    c = TestClient(app)
    inc = new_incident(c)
    body = {"requested_by": "tester"}
    assert c.post(f"/incidents/{inc['id']}/investigate", json=body).status_code == 200
    assert c.post(f"/incidents/{inc['id']}/investigate", json=body).status_code == 429

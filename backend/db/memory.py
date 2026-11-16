"""In-memory repository. Same interface as PostgresRepository.

Used for tests and quick demos (STORAGE=memory). Data is lost on restart.
"""

import copy
import threading
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryRepository:
    name = "memory"

    def __init__(self):
        self._lock = threading.RLock()
        self._incidents: dict[int, dict] = {}
        self._investigations: dict[int, dict] = {}
        self._approvals: dict[int, dict] = {}
        self._audit: list[dict] = []
        self._ids = {"incident": 0, "investigation": 0, "approval": 0, "audit": 0}

    def _next(self, kind: str) -> int:
        self._ids[kind] += 1
        return self._ids[kind]

    # lifecycle
    def open(self):
        pass

    def close(self):
        pass

    def ping(self) -> bool:
        return True

    # incidents
    def create_incident(self, title, description, log_text, severity, created_by):
        with self._lock:
            row = {
                "id": self._next("incident"),
                "title": title,
                "description": description,
                "log_text": log_text,
                "severity": severity,
                "status": "open",
                "created_by": created_by,
                "created_at": _now(),
            }
            self._incidents[row["id"]] = row
            return copy.deepcopy(row)

    def get_incident(self, incident_id):
        with self._lock:
            row = self._incidents.get(incident_id)
            return copy.deepcopy(row) if row else None

    def list_incidents(self, status=None, severity=None, q=None, limit=50, offset=0):
        with self._lock:
            rows = sorted(self._incidents.values(), key=lambda r: -r["id"])
            if status:
                rows = [r for r in rows if r["status"] == status]
            if severity:
                rows = [r for r in rows if r["severity"] == severity]
            if q:
                rows = [r for r in rows if q.lower() in r["title"].lower()]
            total = len(rows)
            return copy.deepcopy(rows[offset : offset + limit]), total

    def update_status(self, incident_id, status):
        with self._lock:
            row = self._incidents.get(incident_id)
            if not row:
                return None
            row["status"] = status
            return copy.deepcopy(row)

    # audit
    def add_audit(self, incident_id, action, actor, details=None):
        with self._lock:
            row = {
                "id": self._next("audit"),
                "incident_id": incident_id,
                "action": action,
                "actor": actor,
                "details": details,
                "created_at": _now(),
            }
            self._audit.append(row)
            return copy.deepcopy(row)

    def list_audit(self, incident_id):
        with self._lock:
            rows = [r for r in self._audit if r["incident_id"] == incident_id]
            return copy.deepcopy(sorted(rows, key=lambda r: -r["id"]))

    # investigations
    def save_investigation(self, incident_id, status, result, created_by):
        with self._lock:
            row = {
                "id": self._next("investigation"),
                "incident_id": incident_id,
                "status": status,
                "result": copy.deepcopy(result),
                "created_by": created_by,
                "created_at": _now(),
            }
            self._investigations[row["id"]] = row
            return copy.deepcopy(row)

    def latest_investigation(self, incident_id):
        with self._lock:
            rows = [r for r in self._investigations.values() if r["incident_id"] == incident_id]
            if not rows:
                return None
            return copy.deepcopy(max(rows, key=lambda r: r["id"]))

    # approvals
    def create_approval(self, incident_id, action, requested_by, investigation_id=None):
        with self._lock:
            row = {
                "id": self._next("approval"),
                "incident_id": incident_id,
                "investigation_id": investigation_id,
                "action": action,
                "requested_by": requested_by,
                "decision": "pending",
                "reviewed_by": None,
                "comments": None,
                "created_at": _now(),
                "reviewed_at": None,
            }
            self._approvals[row["id"]] = row
            return copy.deepcopy(row)

    def get_approval(self, approval_id):
        with self._lock:
            row = self._approvals.get(approval_id)
            return copy.deepcopy(row) if row else None

    def list_approvals(self, decision=None, incident_id=None):
        with self._lock:
            rows = sorted(self._approvals.values(), key=lambda r: -r["id"])
            if decision:
                rows = [r for r in rows if r["decision"] == decision]
            if incident_id:
                rows = [r for r in rows if r["incident_id"] == incident_id]
            return copy.deepcopy(rows)

    def decide_approval(self, approval_id, decision, reviewed_by, comments):
        """Only a pending request can be decided. Returns None otherwise."""
        with self._lock:
            row = self._approvals.get(approval_id)
            if not row or row["decision"] != "pending":
                return None
            row.update(
                decision=decision,
                reviewed_by=reviewed_by,
                comments=comments,
                reviewed_at=_now(),
            )
            return copy.deepcopy(row)

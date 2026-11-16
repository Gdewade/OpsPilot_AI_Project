"""PostgreSQL repository using a psycopg connection pool.

Every method borrows a pooled connection; the transaction is committed
when the `with` block exits normally and rolled back on an exception.
"""

from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


class PostgresRepository:
    name = "postgres"

    def __init__(self, database_url: str, min_size: int = 1, max_size: int = 5):
        if not database_url:
            raise ValueError("DATABASE_URL is required when STORAGE=postgres")
        self.pool = ConnectionPool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    # lifecycle
    def open(self):
        self.pool.open(wait=True, timeout=30)
        with self.pool.connection() as conn:
            conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))

    def close(self):
        self.pool.close()

    def ping(self) -> bool:
        try:
            with self.pool.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _one(self, sql, params=()):
        with self.pool.connection() as conn:
            return conn.execute(sql, params).fetchone()

    def _all(self, sql, params=()):
        with self.pool.connection() as conn:
            return conn.execute(sql, params).fetchall()

    # incidents
    def create_incident(self, title, description, log_text, severity, created_by):
        return self._one(
            """INSERT INTO incidents (title, description, log_text, severity, created_by)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (title, description, log_text, severity, created_by),
        )

    def get_incident(self, incident_id):
        return self._one("SELECT * FROM incidents WHERE id = %s", (incident_id,))

    def list_incidents(self, status=None, severity=None, q=None, limit=50, offset=0):
        where, params = [], []
        if status:
            where.append("status = %s")
            params.append(status)
        if severity:
            where.append("severity = %s")
            params.append(severity)
        if q:
            where.append("title ILIKE %s")
            params.append(f"%{q}%")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        total = self._one(f"SELECT count(*) AS n FROM incidents {clause}", params)["n"]
        rows = self._all(
            f"SELECT * FROM incidents {clause} ORDER BY id DESC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        return rows, total

    def update_status(self, incident_id, status):
        return self._one(
            "UPDATE incidents SET status = %s WHERE id = %s RETURNING *",
            (status, incident_id),
        )

    # audit
    def add_audit(self, incident_id, action, actor, details=None):
        return self._one(
            """INSERT INTO audit_logs (incident_id, action, actor, details)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (incident_id, action, actor, details),
        )

    def list_audit(self, incident_id):
        return self._all(
            "SELECT * FROM audit_logs WHERE incident_id = %s ORDER BY id DESC",
            (incident_id,),
        )

    # investigations
    def save_investigation(self, incident_id, status, result, created_by):
        return self._one(
            """INSERT INTO investigations (incident_id, status, result, created_by)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (incident_id, status, Jsonb(result), created_by),
        )

    def latest_investigation(self, incident_id):
        return self._one(
            "SELECT * FROM investigations WHERE incident_id = %s ORDER BY id DESC LIMIT 1",
            (incident_id,),
        )

    # approvals
    def create_approval(self, incident_id, action, requested_by, investigation_id=None):
        return self._one(
            """INSERT INTO approval_requests
                   (incident_id, investigation_id, action, requested_by)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (incident_id, investigation_id, action, requested_by),
        )

    def get_approval(self, approval_id):
        return self._one("SELECT * FROM approval_requests WHERE id = %s", (approval_id,))

    def list_approvals(self, decision=None, incident_id=None):
        where, params = [], []
        if decision:
            where.append("decision = %s")
            params.append(decision)
        if incident_id:
            where.append("incident_id = %s")
            params.append(incident_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return self._all(
            f"SELECT * FROM approval_requests {clause} ORDER BY id DESC", params
        )

    def decide_approval(self, approval_id, decision, reviewed_by, comments):
        """Atomic: only a still-pending request is updated, so a request
        can never be decided twice even with concurrent reviewers."""
        return self._one(
            """UPDATE approval_requests
               SET decision = %s, reviewed_by = %s, comments = %s, reviewed_at = now()
               WHERE id = %s AND decision = 'pending'
               RETURNING *""",
            (decision, reviewed_by, comments, approval_id),
        )

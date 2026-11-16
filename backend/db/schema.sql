-- OpsPilot AI schema. Applied automatically at startup (idempotent).

CREATE TABLE IF NOT EXISTS incidents (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(150) NOT NULL,
    description TEXT         NOT NULL,
    log_text    TEXT         NOT NULL,
    severity    VARCHAR(20)  NOT NULL DEFAULT 'medium'
                CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status      VARCHAR(30)  NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'investigating', 'needs_human', 'resolved')),
    created_by  VARCHAR(100) NOT NULL DEFAULT 'unknown',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS investigations (
    id          SERIAL PRIMARY KEY,
    incident_id INTEGER     NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    status      VARCHAR(30) NOT NULL,
    result      JSONB       NOT NULL,
    created_by  VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id               SERIAL PRIMARY KEY,
    incident_id      INTEGER      NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    investigation_id INTEGER      REFERENCES investigations(id) ON DELETE SET NULL,
    action           TEXT         NOT NULL,
    requested_by     VARCHAR(100) NOT NULL,
    decision         VARCHAR(20)  NOT NULL DEFAULT 'pending'
                     CHECK (decision IN ('pending', 'approved', 'rejected')),
    reviewed_by      VARCHAR(100),
    comments         TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    reviewed_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    incident_id INTEGER      NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    action      VARCHAR(60)  NOT NULL,
    actor       VARCHAR(100) NOT NULL,
    details     TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incidents_status   ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents (severity);
CREATE INDEX IF NOT EXISTS idx_inv_incident       ON investigations (incident_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_approvals_decision ON approval_requests (decision);
CREATE INDEX IF NOT EXISTS idx_audit_incident     ON audit_logs (incident_id, id DESC);

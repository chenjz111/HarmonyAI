-- 0002_v3_session_activity (Owner Flow Amendment 001 §4.1 / §4.2)
-- Session activity state + immutable Understanding snapshots.

CREATE TABLE IF NOT EXISTS v3_session_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    internal_user_pk INTEGER NOT NULL,
    flow_contract_version VARCHAR(32),
    input_mode VARCHAR(16),
    input_revision INTEGER NOT NULL DEFAULT 1,
    active_document_id VARCHAR(64),
    understanding_ref TEXT,
    questionnaire_ref TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CHECK (input_revision >= 1),
    CHECK (input_mode IS NULL OR input_mode IN ('with_document', 'without_document'))
);

CREATE INDEX IF NOT EXISTS ix_v3_session_activity_owner
ON v3_session_activities(internal_user_pk);

CREATE TABLE IF NOT EXISTS v3_understanding_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    understanding_id VARCHAR(64) NOT NULL,
    revision INTEGER NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    internal_user_pk INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL,
    snapshot_json TEXT NOT NULL,
    safety_policy VARCHAR(32),
    safety_evaluation_status VARCHAR(32),
    safety_status VARCHAR(32),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (understanding_id, revision),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CHECK (revision >= 1)
);

CREATE INDEX IF NOT EXISTS ix_v3_understanding_owner
ON v3_understanding_snapshots(internal_user_pk, understanding_id);

-- Exact idempotent replay: store the success payload on the idempotency record.
ALTER TABLE idempotency_records ADD COLUMN response_json TEXT;

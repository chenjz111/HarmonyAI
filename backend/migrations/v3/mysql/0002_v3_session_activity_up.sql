-- 0002_v3_session_activity (Owner Flow Amendment 001 §4.1 / §4.2)
-- Session activity state + immutable Understanding snapshots.

CREATE TABLE IF NOT EXISTS v3_session_activities (
    id BIGINT NOT NULL AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    internal_user_pk INTEGER NOT NULL,
    flow_contract_version VARCHAR(32) NULL,
    input_mode VARCHAR(16) NULL,
    input_revision INTEGER NOT NULL DEFAULT 1,
    active_document_id VARCHAR(64) NULL,
    understanding_ref TEXT NULL,
    questionnaire_ref TEXT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_v3_session_activity_session (session_id),
    KEY ix_v3_session_activity_owner (internal_user_pk),
    CONSTRAINT fk_v3_session_activity_session
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_v3_session_activity_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_v3_session_activity_revision CHECK (input_revision >= 1),
    CONSTRAINT ck_v3_session_activity_mode CHECK (
        input_mode IS NULL OR input_mode IN ('with_document', 'without_document')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS v3_understanding_snapshots (
    id BIGINT NOT NULL AUTO_INCREMENT,
    understanding_id VARCHAR(64) NOT NULL,
    revision INTEGER NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    internal_user_pk INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL,
    snapshot_json LONGTEXT NOT NULL,
    safety_policy VARCHAR(32) NULL,
    safety_evaluation_status VARCHAR(32) NULL,
    safety_status VARCHAR(32) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_v3_understanding_revision (understanding_id, revision),
    KEY ix_v3_understanding_owner (internal_user_pk, understanding_id),
    CONSTRAINT fk_v3_understanding_session
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_v3_understanding_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_v3_understanding_revision CHECK (revision >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Exact idempotent replay: store the success payload on the idempotency record.
-- V3_IDEMPOTENCY_RESPONSE_JSON_BEGIN
ALTER TABLE idempotency_records
    ADD COLUMN response_json TEXT NULL;
-- V3_IDEMPOTENCY_RESPONSE_JSON_END

-- ============================================================
-- 0006_v3_relevance — per-set document relevance result (MySQL 8)
-- Mirrors frozen DocumentRelevanceResult: one result per (set, revision)
-- with a single outcome + reason_code/reason; downstream gates derived.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_relevances (
    document_relevance_id VARCHAR(64) PRIMARY KEY,
    document_set_id VARCHAR(64) NOT NULL,
    document_set_revision INTEGER NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    revision INTEGER NOT NULL,
    outcome VARCHAR(16) NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    reason TEXT NOT NULL,
    evaluator VARCHAR(32) NULL,
    evaluator_version VARCHAR(32) NULL,
    evaluated_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_document_relevances_set
        FOREIGN KEY (document_set_id)
        REFERENCES document_sets(document_set_id) ON DELETE CASCADE,
    CONSTRAINT uq_document_relevances_revision
        UNIQUE (document_set_id, revision),
    CONSTRAINT ck_document_relevances_outcome
        CHECK (outcome IN ('VALID', 'INVALID', 'IRRELEVANT', 'INSUFFICIENT'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_document_relevances_set
    ON document_relevances(document_set_id);

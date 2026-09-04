-- ============================================================
-- 0006_v3_relevance — document relevance assessment (MySQL 8)
-- Mirrors Issue #99 ruling: outcome enum + per-source audit.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_relevances (
    document_relevance_id VARCHAR(64) PRIMARY KEY,
    document_set_id VARCHAR(64) NOT NULL,
    document_set_revision INTEGER NOT NULL,
    document_id VARCHAR(64) NOT NULL,
    outcome VARCHAR(16) NOT NULL,
    reason_codes_json JSON NOT NULL,
    evaluator VARCHAR(32) NULL,
    evaluator_version VARCHAR(32) NULL,
    evaluated_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_document_relevances_set
        FOREIGN KEY (document_set_id)
        REFERENCES document_sets(document_set_id) ON DELETE CASCADE,
    CONSTRAINT uq_document_relevances_document
        UNIQUE (document_set_id, document_id),
    CONSTRAINT ck_document_relevances_outcome
        CHECK (outcome IN ('VALID', 'INVALID', 'IRRELEVANT', 'INSUFFICIENT'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_document_relevances_set
    ON document_relevances(document_set_id);

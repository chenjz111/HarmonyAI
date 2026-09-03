PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- ============================================================
-- 0005_v3_relevance — document relevance assessment (SQLite)
-- Mirrors Issue #99 ruling: outcome enum + per-source audit.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_relevances (
    document_relevance_id TEXT PRIMARY KEY,
    document_set_id TEXT NOT NULL,
    document_set_revision INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL,
    evaluator TEXT,
    evaluator_version TEXT,
    evaluated_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_set_id) REFERENCES document_sets(document_set_id) ON DELETE CASCADE,
    UNIQUE (document_set_id, document_id),
    CHECK (outcome IN ('VALID', 'INVALID', 'IRRELEVANT', 'INSUFFICIENT'))
);
CREATE INDEX IF NOT EXISTS ix_document_relevances_set
    ON document_relevances(document_set_id);

COMMIT;
PRAGMA foreign_keys=ON;

PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- ============================================================
-- 0006_v3_relevance — per-set document relevance result (SQLite)
-- Mirrors frozen DocumentRelevanceResult: one result per (set, revision)
-- with a single outcome + reason_code/reason; downstream gates derived.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_relevances (
    document_relevance_id TEXT PRIMARY KEY,
    document_set_id TEXT NOT NULL,
    document_set_revision INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    reason TEXT NOT NULL,
    evaluator TEXT,
    evaluator_version TEXT,
    evaluated_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_set_id) REFERENCES document_sets(document_set_id) ON DELETE CASCADE,
    UNIQUE (document_set_id, revision),
    CHECK (outcome IN ('VALID', 'INVALID', 'IRRELEVANT', 'INSUFFICIENT'))
);
CREATE INDEX IF NOT EXISTS ix_document_relevances_set
    ON document_relevances(document_set_id);

COMMIT;
PRAGMA foreign_keys=ON;

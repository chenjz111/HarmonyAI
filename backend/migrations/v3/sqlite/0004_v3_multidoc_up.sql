PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- ============================================================
-- 0004_v3_multidoc — multi-document sets (SQLite)
-- Mirrors Issue #99 ruling: 1-3 ordered documents per set.
-- The sessions.active_document_set_id column is added idempotently by
-- sprint4_migrations; this migration only creates the two new tables.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_sets (
    document_set_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    UNIQUE (session_row_id, document_set_id),
    CHECK (revision >= 1),
    CHECK (status IN ('active', 'superseded', 'discarded'))
);
CREATE INDEX IF NOT EXISTS ix_document_sets_user
    ON document_sets(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_document_sets_session
    ON document_sets(session_row_id);

CREATE TABLE IF NOT EXISTS document_set_items (
    document_set_item_id TEXT PRIMARY KEY,
    document_set_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_set_id) REFERENCES document_sets(document_set_id) ON DELETE CASCADE,
    UNIQUE (document_set_id, position),
    UNIQUE (document_set_id, document_id),
    CHECK (position >= 1 AND position <= 3)
);
CREATE INDEX IF NOT EXISTS ix_document_set_items_set
    ON document_set_items(document_set_id);

COMMIT;
PRAGMA foreign_keys=ON;

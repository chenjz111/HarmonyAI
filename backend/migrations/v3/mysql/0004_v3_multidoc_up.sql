-- ============================================================
-- 0004_v3_multidoc — multi-document sets (MySQL 8)
-- Mirrors Issue #99 ruling: 1-3 ordered documents per set.
-- sessions.active_document_set_id is added idempotently by
-- sprint4_migrations; this migration only creates the two new tables.
-- ============================================================

CREATE TABLE IF NOT EXISTS document_sets (
    document_set_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_document_sets_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_document_sets_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    CONSTRAINT uq_document_sets_session
        UNIQUE (session_row_id, document_set_id),
    CONSTRAINT ck_document_sets_revision
        CHECK (revision >= 1),
    CONSTRAINT ck_document_sets_status
        CHECK (status IN ('active', 'superseded', 'discarded'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_document_sets_user
    ON document_sets(internal_user_pk, created_at DESC);
CREATE INDEX ix_document_sets_session
    ON document_sets(session_row_id);

CREATE TABLE IF NOT EXISTS document_set_items (
    document_set_item_id VARCHAR(64) PRIMARY KEY,
    document_set_id VARCHAR(64) NOT NULL,
    document_id VARCHAR(64) NOT NULL,
    position INTEGER NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_document_set_items_set
        FOREIGN KEY (document_set_id)
        REFERENCES document_sets(document_set_id) ON DELETE CASCADE,
    CONSTRAINT uq_document_set_items_position
        UNIQUE (document_set_id, position),
    CONSTRAINT uq_document_set_items_document
        UNIQUE (document_set_id, document_id),
    CONSTRAINT ck_document_set_items_position
        CHECK (position >= 1 AND position <= 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_document_set_items_set
    ON document_set_items(document_set_id);

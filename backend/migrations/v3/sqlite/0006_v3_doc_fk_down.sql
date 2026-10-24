PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

ALTER TABLE document_set_items RENAME TO document_set_items_old;
CREATE TABLE document_set_items (
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
INSERT INTO document_set_items (document_set_item_id, document_set_id, document_id, position, created_at)
SELECT document_set_item_id, document_set_id, document_id, position, created_at
FROM document_set_items_old;
DROP TABLE document_set_items_old;
CREATE INDEX IF NOT EXISTS ix_document_set_items_set
    ON document_set_items(document_set_id);

DELETE FROM schema_migrations WHERE version = '0006_v3_doc_fk';
COMMIT;
PRAGMA foreign_keys=ON;

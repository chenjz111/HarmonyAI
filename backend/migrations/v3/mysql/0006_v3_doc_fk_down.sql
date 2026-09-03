-- 0006_v3_doc_fk rollback.

ALTER TABLE document_set_items DROP FOREIGN KEY fk_document_set_items_document;

DELETE FROM schema_migrations WHERE version = '0006_v3_doc_fk';

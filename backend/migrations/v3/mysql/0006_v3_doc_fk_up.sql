-- 0006_v3_doc_fk — add the real FK document_set_items.document_id ->
-- documents.document_id.

ALTER TABLE document_set_items
    ADD CONSTRAINT fk_document_set_items_document
        FOREIGN KEY (document_id) REFERENCES documents(document_id);

-- 0005_v3_relevance rollback.

DROP TABLE IF EXISTS document_relevances;

DELETE FROM schema_migrations WHERE version = '0005_v3_relevance';

PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

DROP TABLE IF EXISTS document_relevances;

DELETE FROM schema_migrations WHERE version = '0006_v3_relevance';
COMMIT;
PRAGMA foreign_keys=ON;

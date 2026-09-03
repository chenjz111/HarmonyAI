PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

DROP TABLE IF EXISTS document_set_items;
DROP TABLE IF EXISTS document_sets;

DELETE FROM schema_migrations WHERE version = '0004_v3_multidoc';
COMMIT;
PRAGMA foreign_keys=ON;

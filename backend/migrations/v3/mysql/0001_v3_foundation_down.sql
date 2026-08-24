ALTER TABLE sessions DROP FOREIGN KEY fk_sessions_users;
DROP INDEX ix_sessions_user_created ON sessions;
ALTER TABLE sessions DROP COLUMN flow_version;
DROP TABLE IF EXISTS idempotency_records;
DROP TABLE IF EXISTS user_profiles;
DROP TABLE IF EXISTS user_identities;
DELETE FROM schema_migrations WHERE version = '0001_v3_foundation';

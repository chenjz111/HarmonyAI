PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

DROP TABLE IF EXISTS idempotency_records;
DROP TABLE IF EXISTS user_profiles;
DROP TABLE IF EXISTS user_identities;

ALTER TABLE sessions RENAME TO sessions_v3_backup;
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(16) DEFAULT 'active',
    current_agent VARCHAR(32),
    metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO sessions (
    id, user_id, session_id, status, current_agent, metadata_json,
    created_at, updated_at
)
SELECT
    id, user_id, session_id, status, current_agent, metadata_json,
    created_at, updated_at
FROM sessions_v3_backup;
DROP TABLE sessions_v3_backup;
CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_session_id ON sessions(session_id);

DELETE FROM schema_migrations WHERE version = '0001_v3_foundation';
COMMIT;
PRAGMA foreign_keys=ON;

PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

INSERT OR IGNORE INTO users (id, openid, nickname)
VALUES (1, 'legacy:demo:v2-default', NULL);

-- V3_SESSION_UPGRADE_BEGIN
INSERT OR IGNORE INTO users (id, openid, nickname)
SELECT DISTINCT user_id, 'legacy:migrated:' || user_id, NULL
FROM sessions
WHERE user_id NOT IN (SELECT id FROM users);

ALTER TABLE sessions RENAME TO sessions_v2_backup;

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(16) DEFAULT 'active',
    current_agent VARCHAR(32),
    metadata_json TEXT,
    flow_version VARCHAR(16),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO sessions (
    id, user_id, session_id, status, current_agent, metadata_json,
    flow_version, created_at, updated_at
)
SELECT
    id, user_id, session_id, status, current_agent, metadata_json,
    {{FLOW_VERSION_SELECT}}, created_at, updated_at
FROM sessions_v2_backup;

DROP TABLE sessions_v2_backup;
CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_session_id ON sessions(session_id);
-- V3_SESSION_UPGRADE_END

CREATE INDEX IF NOT EXISTS ix_sessions_user_created
ON sessions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_identities (
    internal_user_pk INTEGER PRIMARY KEY,
    public_user_id VARCHAR(64) NOT NULL UNIQUE,
    auth_type VARCHAR(16) NOT NULL,
    guest_expires_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CHECK (auth_type IN ('registered', 'guest')),
    CHECK (
        (auth_type = 'guest' AND guest_expires_at IS NOT NULL)
        OR (auth_type = 'registered' AND guest_expires_at IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS user_profiles (
    internal_user_pk INTEGER PRIMARY KEY,
    nickname VARCHAR(64),
    avatar_storage_key VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_record_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    operation VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_hash VARCHAR(96) NOT NULL,
    resource_type VARCHAR(32),
    resource_id VARCHAR(64),
    status VARCHAR(16) NOT NULL,
    response_code INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (internal_user_pk, operation, idempotency_key),
    CHECK (status IN ('processing', 'succeeded', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_user_identities_public_user_id
ON user_identities(public_user_id);
CREATE INDEX IF NOT EXISTS ix_idempotency_owner_operation
ON idempotency_records(internal_user_pk, operation, idempotency_key);

COMMIT;
PRAGMA foreign_keys=ON;

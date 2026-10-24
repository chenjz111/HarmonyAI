CREATE TABLE IF NOT EXISTS user_identities (
    internal_user_pk INTEGER PRIMARY KEY,
    public_user_id VARCHAR(64) NOT NULL UNIQUE,
    auth_type VARCHAR(16) NOT NULL,
    guest_expires_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_user_identities_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_user_identities_auth_type
        CHECK (auth_type IN ('registered', 'guest')),
    CONSTRAINT ck_user_identities_guest_expiry
        CHECK (
            (auth_type = 'guest' AND guest_expires_at IS NOT NULL)
            OR (auth_type = 'registered' AND guest_expires_at IS NULL)
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_profiles (
    internal_user_pk INTEGER PRIMARY KEY,
    nickname VARCHAR(64) NULL,
    avatar_storage_key VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_user_profiles_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_record_id VARCHAR(64) PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    operation VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    request_hash VARCHAR(96) NOT NULL,
    resource_type VARCHAR(32) NULL,
    resource_id VARCHAR(64) NULL,
    status VARCHAR(16) NOT NULL,
    response_code INTEGER NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_idempotency_records_user
        FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_idempotency_owner_operation
        UNIQUE (internal_user_pk, operation, idempotency_key),
    CONSTRAINT ck_idempotency_status
        CHECK (status IN ('processing', 'succeeded', 'failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO users (id, openid, nickname)
VALUES (1, 'legacy:demo:v2-default', NULL);

INSERT IGNORE INTO users (id, openid, nickname)
SELECT DISTINCT user_id, CONCAT('legacy:migrated:', user_id), NULL
FROM sessions;

-- V3_SESSION_FLOW_BEGIN
ALTER TABLE sessions ADD COLUMN flow_version VARCHAR(16) NULL;
-- V3_SESSION_FLOW_END

-- V3_SESSION_FK_BEGIN
ALTER TABLE sessions
ADD CONSTRAINT fk_sessions_users
FOREIGN KEY (user_id) REFERENCES users(id);
-- V3_SESSION_FK_END

-- V3_SESSION_OWNER_INDEX_BEGIN
CREATE INDEX ix_sessions_user_created
ON sessions(user_id, created_at DESC);
-- V3_SESSION_OWNER_INDEX_END

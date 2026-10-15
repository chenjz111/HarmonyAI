-- Storage only. No refresh issuer, token algorithm, TTL or login enabled.
ALTER TABLE user_identities ADD COLUMN auth_epoch INTEGER NOT NULL DEFAULT 0 CONSTRAINT ck_user_identities_auth_epoch CHECK(auth_epoch>=0);
CREATE TABLE IF NOT EXISTS auth_sessions (
 auth_session_id VARCHAR(64) NOT NULL PRIMARY KEY,
 internal_user_pk INTEGER NOT NULL,
 refresh_credential_hash VARCHAR(255) NOT NULL,
 family_id VARCHAR(64) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 expires_at DATETIME NOT NULL,
 revoked_at DATETIME NULL,
 CONSTRAINT fk_auth_sessions_owner FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT uq_auth_sessions_refresh_hash UNIQUE(refresh_credential_hash),
 CONSTRAINT ck_auth_sessions_hash_nonempty CHECK(length(refresh_credential_hash)>0),
 CONSTRAINT ck_auth_sessions_expiry CHECK(expires_at>created_at),
 CONSTRAINT ck_auth_sessions_revocation CHECK(revoked_at IS NULL OR revoked_at>=created_at)
);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_owner ON auth_sessions(internal_user_pk);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_family ON auth_sessions(family_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expiry ON auth_sessions(expires_at);

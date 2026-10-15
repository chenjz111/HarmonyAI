-- MySQL >=8.0.16. Storage only; DDL implicitly commits.
ALTER TABLE user_identities ADD COLUMN auth_epoch INTEGER NOT NULL DEFAULT 0 CONSTRAINT ck_user_identities_auth_epoch CHECK(auth_epoch>=0);
CREATE TABLE IF NOT EXISTS auth_sessions (
 auth_session_id VARCHAR(64) NOT NULL PRIMARY KEY,
 internal_user_pk INT NOT NULL,
 refresh_credential_hash VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
 family_id VARCHAR(64) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6) NULL,
 CONSTRAINT fk_auth_sessions_owner FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT uq_auth_sessions_refresh_hash UNIQUE(refresh_credential_hash),
 CONSTRAINT ck_auth_sessions_hash_nonempty CHECK(length(refresh_credential_hash)>0),
 CONSTRAINT ck_auth_sessions_expiry CHECK(expires_at>created_at),
 CONSTRAINT ck_auth_sessions_revocation CHECK(revoked_at IS NULL OR revoked_at>=created_at),
 INDEX ix_auth_sessions_owner(internal_user_pk),
 INDEX ix_auth_sessions_family(family_id),
 INDEX ix_auth_sessions_expiry(expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

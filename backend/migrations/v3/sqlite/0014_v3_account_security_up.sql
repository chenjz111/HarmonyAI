-- Formal0014 Owner Account Security R1; routes remain disabled pending acceptance.
CREATE TABLE account_credentials (
	internal_user_pk INTEGER NOT NULL, 
	username VARCHAR(32) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (internal_user_pk), 
	CONSTRAINT ck_account_username_length CHECK (length(username) BETWEEN 3 AND 32), 
	CONSTRAINT ck_account_username_sqlite CHECK (username = lower(username) AND username NOT GLOB '*[^a-z0-9_]*'), 
	FOREIGN KEY(internal_user_pk) REFERENCES user_identities (internal_user_pk) ON DELETE RESTRICT, 
	UNIQUE (username)
);
CREATE TABLE registered_session_state (
	auth_session_id VARCHAR(64) NOT NULL, 
	absolute_expires_at DATETIME NOT NULL, 
	csrf_hash VARCHAR(71) NOT NULL, 
	platform VARCHAR(8) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (auth_session_id), 
	CONSTRAINT ck_registered_absolute_expiry CHECK (absolute_expires_at > created_at), 
	CONSTRAINT ck_registered_platform CHECK (platform IN ('android','h5')), 
	FOREIGN KEY(auth_session_id) REFERENCES auth_sessions (auth_session_id) ON DELETE RESTRICT
);
CREATE TABLE auth_refresh_proofs (
	credential_hash VARCHAR(71) NOT NULL, 
	auth_session_id VARCHAR(64) NOT NULL, 
	issued_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	consumed_at DATETIME, 
	PRIMARY KEY (credential_hash), 
	CONSTRAINT ck_refresh_expiry CHECK (expires_at > issued_at), 
	CONSTRAINT ck_refresh_consumed CHECK (consumed_at IS NULL OR consumed_at >= issued_at), 
	FOREIGN KEY(auth_session_id) REFERENCES auth_sessions (auth_session_id) ON DELETE RESTRICT
);
CREATE INDEX ix_refresh_proofs_session ON auth_refresh_proofs (auth_session_id);
CREATE TABLE account_login_buckets (
	bucket_key VARCHAR(71) NOT NULL, 
	kind VARCHAR(8) NOT NULL, 
	window_started_at DATETIME NOT NULL, 
	attempts INTEGER NOT NULL, 
	failures INTEGER NOT NULL, 
	next_allowed_at DATETIME, 
	PRIMARY KEY (bucket_key), 
	CONSTRAINT ck_login_bucket_kind CHECK (kind IN ('account','source')), 
	CONSTRAINT ck_login_bucket_counts CHECK (attempts >= 0 AND failures >= 0)
);

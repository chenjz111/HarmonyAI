-- NOT an atomic rollback. Approved operator preflight is mandatory:
-- auth_sessions empty; all auth_epoch=0; no later migration; verified backup.
-- Real MySQL execution/recovery NOT verified by this package.
DROP TABLE auth_sessions;
ALTER TABLE user_identities DROP CHECK ck_user_identities_auth_epoch, DROP COLUMN auth_epoch;
DELETE FROM schema_migrations WHERE version='0011_v3_auth_foundation';

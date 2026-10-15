-- Requires SQLite >=3.35. Caller owns transaction; refuse any credential/epoch loss.
-- Execute only through rollback_auth_foundation: it first rejects definitions
-- (including ORM fresh-create table CHECKs) incompatible with DROP auth_epoch.
CREATE TEMP TABLE auth_0011_down_guard(ok INTEGER NOT NULL CHECK(ok=1));
INSERT INTO auth_0011_down_guard SELECT CASE WHEN
 (SELECT count(*) FROM auth_sessions)=0 AND
 (SELECT count(*) FROM user_identities WHERE auth_epoch!=0)=0 AND
 (SELECT count(*) FROM schema_migrations WHERE version>'0011_v3_auth_foundation')=0
 THEN 1 ELSE 0 END;
DROP TABLE auth_0011_down_guard;
DROP TABLE auth_sessions;
ALTER TABLE user_identities DROP COLUMN auth_epoch;
DELETE FROM schema_migrations WHERE version='0011_v3_auth_foundation';

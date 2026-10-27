-- Formal 0013 safe downgrade entry marker; not standalone destructive SQL.
-- Use backend.app.core.v3_migrations.rollback_feedback_consent(engine).
-- Requires latest0013/checksum, intact schema, no extension evidence/tombstones,
-- no unknown dependencies, and a successful schema-only DROP COLUMN probe.
-- Never rebuild old feedback/profile tables or discard retained keys blindly.
SELECT harmonyai_0013_requires_verified_downgrade_executor();

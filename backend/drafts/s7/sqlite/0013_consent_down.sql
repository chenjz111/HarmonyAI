-- UNREGISTERED DRAFT: SQLite >=3.35; refuse any non-default extension data.
DROP INDEX ix_feedback_owner_deleted;
ALTER TABLE feedback_v3 DROP COLUMN learning_consent;
ALTER TABLE feedback_v3 DROP COLUMN request_fingerprint;
ALTER TABLE feedback_v3 DROP COLUMN evidence_epoch;
ALTER TABLE feedback_v3 DROP COLUMN source_task_id;
ALTER TABLE feedback_v3 DROP COLUMN deleted_at;
ALTER TABLE feedback_v3 DROP COLUMN consented_at;
ALTER TABLE feedback_v3 DROP COLUMN consent_policy_version;
ALTER TABLE user_music_preference_versions DROP COLUMN evidence_epoch;

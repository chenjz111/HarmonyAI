-- UNREGISTERED DRAFT. Preflight must refuse all non-default extension data.
ALTER TABLE feedback_v3
 DROP FOREIGN KEY fk_feedback_source_task,
 DROP CHECK ck_feedback_consent,
 DROP CHECK ck_feedback_evidence_epoch,
 DROP INDEX ix_feedback_owner_deleted,
 DROP COLUMN learning_consent,
 DROP COLUMN request_fingerprint,
 DROP COLUMN evidence_epoch,
 DROP COLUMN source_task_id,
 DROP COLUMN deleted_at,
 DROP COLUMN consented_at,
 DROP COLUMN consent_policy_version;
ALTER TABLE user_music_preference_versions
 DROP CHECK ck_preference_evidence_epoch,
 DROP COLUMN evidence_epoch;

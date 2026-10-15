-- UNREGISTERED DRAFT. Legacy rows retain false/null and original contents.
ALTER TABLE feedback_v3 ADD COLUMN consent_policy_version VARCHAR(64) NULL;
ALTER TABLE feedback_v3 ADD COLUMN consented_at DATETIME NULL;
ALTER TABLE feedback_v3 ADD COLUMN deleted_at DATETIME NULL;
ALTER TABLE feedback_v3 ADD COLUMN source_task_id VARCHAR(64) NULL REFERENCES generation_tasks(task_id);
ALTER TABLE feedback_v3 ADD COLUMN evidence_epoch BIGINT NULL CHECK(evidence_epoch IS NULL OR evidence_epoch>=0);
ALTER TABLE feedback_v3 ADD COLUMN request_fingerprint VARCHAR(96) NULL;
ALTER TABLE feedback_v3 ADD COLUMN learning_consent INTEGER NOT NULL DEFAULT 0 CONSTRAINT ck_feedback_consent CHECK(
 (learning_consent=0 AND consent_policy_version IS NULL AND consented_at IS NULL) OR
 (learning_consent=1 AND consent_policy_version IS NOT NULL AND length(consent_policy_version)>0 AND consented_at IS NOT NULL AND evidence_epoch IS NOT NULL AND source_task_id IS NOT NULL)
);
ALTER TABLE user_music_preference_versions ADD COLUMN evidence_epoch BIGINT NULL CHECK(evidence_epoch IS NULL OR evidence_epoch>=0);
CREATE INDEX ix_feedback_owner_deleted ON feedback_v3(internal_user_pk,deleted_at,created_at);

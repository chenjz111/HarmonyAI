-- UNREGISTERED DRAFT; legacy false/null. Requires existing parent key types/collations.
ALTER TABLE feedback_v3
 ADD COLUMN consent_policy_version VARCHAR(64) NULL,
 ADD COLUMN consented_at DATETIME(6) NULL,
 ADD COLUMN deleted_at DATETIME(6) NULL,
 ADD COLUMN source_task_id VARCHAR(64) NULL,
 ADD COLUMN evidence_epoch BIGINT NULL,
 ADD COLUMN request_fingerprint VARCHAR(96) NULL,
 ADD COLUMN learning_consent INT NOT NULL DEFAULT 0,
 ADD CONSTRAINT fk_feedback_source_task FOREIGN KEY(source_task_id) REFERENCES generation_tasks(task_id),
 ADD CONSTRAINT ck_feedback_evidence_epoch CHECK(evidence_epoch IS NULL OR evidence_epoch>=0),
 ADD CONSTRAINT ck_feedback_consent CHECK(
  (learning_consent=0 AND consent_policy_version IS NULL AND consented_at IS NULL) OR
  (learning_consent=1 AND consent_policy_version IS NOT NULL AND length(consent_policy_version)>0 AND consented_at IS NOT NULL AND evidence_epoch IS NOT NULL AND source_task_id IS NOT NULL)
 ),
 ADD INDEX ix_feedback_owner_deleted(internal_user_pk,deleted_at,created_at);
ALTER TABLE user_music_preference_versions
 ADD COLUMN evidence_epoch BIGINT NULL,
 ADD CONSTRAINT ck_preference_evidence_epoch CHECK(evidence_epoch IS NULL OR evidence_epoch>=0);

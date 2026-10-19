-- UNREGISTERED TEMPLATE. MySQL >=8.0.16, InnoDB only. Render from actual metadata.
-- NOT RUN. DDL implicit commits: no claim of all-or-none rollback.
ALTER TABLE feedback_v3
 ADD COLUMN consent_policy_version VARCHAR(64) NULL,
 ADD COLUMN consented_at DATETIME(6) NULL,
 ADD COLUMN deleted_at DATETIME(6) NULL,
 ADD COLUMN source_task_id {{TASK_ID_TYPE}} NULL,
 ADD COLUMN playback_event_row_id {{EVENT_ROW_TYPE}} NULL,
 ADD COLUMN evidence_epoch BIGINT NULL,
 ADD COLUMN request_fingerprint VARCHAR(71) CHARACTER SET ascii COLLATE ascii_bin NULL,
 ADD COLUMN learning_consent INT NOT NULL DEFAULT 0,
 ADD CONSTRAINT int2_0013_consent CHECK(learning_consent IN (0,1) AND
 ((learning_consent=0 AND consent_policy_version IS NULL AND consented_at IS NULL)
 OR (learning_consent=1 AND consent_policy_version IS NOT NULL AND CHAR_LENGTH(consent_policy_version) BETWEEN 1 AND 64 AND consented_at IS NOT NULL AND evidence_epoch IS NOT NULL AND source_task_id IS NOT NULL AND playback_event_row_id IS NOT NULL AND request_fingerprint IS NOT NULL))),
 ADD CONSTRAINT int2_0013_epoch CHECK(evidence_epoch IS NULL OR evidence_epoch>=0),
 ADD CONSTRAINT int2_0013_fingerprint CHECK(request_fingerprint IS NULL OR (CHAR_LENGTH(request_fingerprint)=71 AND LEFT(request_fingerprint,7)='sha256:' AND SUBSTRING(request_fingerprint,8) REGEXP '^[0-9a-f]+$')),
 ADD CONSTRAINT int2_0013_event_context CHECK(playback_event_row_id IS NULL OR source_task_id IS NOT NULL),
 ADD CONSTRAINT int2_0013_task_fk FOREIGN KEY(source_task_id,internal_user_pk,music_asset_id) REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id) ON DELETE RESTRICT,
 ADD INDEX int2_0013_feedback_owner_deleted(internal_user_pk,deleted_at,created_at,feedback_id);
CREATE UNIQUE INDEX int2_0013_playback_proof_key ON music_playback_events(playback_event_row_id,internal_user_pk,music_asset_id,source_context_id);
ALTER TABLE feedback_v3 ADD CONSTRAINT int2_0013_event_fk FOREIGN KEY(playback_event_row_id,internal_user_pk,music_asset_id,source_task_id) REFERENCES music_playback_events(playback_event_row_id,internal_user_pk,music_asset_id,source_context_id) ON DELETE RESTRICT;
ALTER TABLE user_music_preference_versions ADD COLUMN evidence_epoch BIGINT NULL, ADD CONSTRAINT int2_0013_version_epoch CHECK(evidence_epoch IS NULL OR evidence_epoch>=0);
-- Each following CREATE TRIGGER is ONE driver statement; do not split at ';'.
CREATE TRIGGER int2_0013_feedback_immutable BEFORE UPDATE ON feedback_v3 FOR EACH ROW
BEGIN
 IF NOT(CAST(NEW.feedback_id AS BINARY) <=> CAST(OLD.feedback_id AS BINARY)) OR NOT(NEW.internal_user_pk <=> OLD.internal_user_pk) OR NOT(CAST(NEW.idempotency_key AS BINARY) <=> CAST(OLD.idempotency_key AS BINARY))
 OR NOT(CAST(NEW.music_asset_id AS BINARY) <=> CAST(OLD.music_asset_id AS BINARY)) OR NOT(NEW.session_row_id <=> OLD.session_row_id)
 OR NOT(NEW.learning_consent <=> OLD.learning_consent) OR NOT(CAST(NEW.consent_policy_version AS BINARY) <=> CAST(OLD.consent_policy_version AS BINARY))
 OR NOT(NEW.consented_at <=> OLD.consented_at) OR NOT(CAST(NEW.source_task_id AS BINARY) <=> CAST(OLD.source_task_id AS BINARY))
 OR NOT(NEW.playback_event_row_id <=> OLD.playback_event_row_id) OR NOT(NEW.evidence_epoch <=> OLD.evidence_epoch)
 OR NOT(NEW.request_fingerprint <=> OLD.request_fingerprint) OR (OLD.deleted_at IS NOT NULL AND NOT(NEW.deleted_at <=> OLD.deleted_at))
 OR (OLD.request_fingerprint IS NOT NULL AND (
 NOT(CAST(NEW.change_label AS BINARY) <=> CAST(OLD.change_label AS BINARY))
 OR NOT(CAST(NEW.pre_state_snapshot_json AS BINARY) <=> CAST(OLD.pre_state_snapshot_json AS BINARY))
 OR NOT(CAST(NEW.post_state_json AS BINARY) <=> CAST(OLD.post_state_json AS BINARY))
 OR NOT(CAST(NEW.experience_json AS BINARY) <=> CAST(OLD.experience_json AS BINARY))
 OR NOT(CAST(NEW.continue_use AS BINARY) <=> CAST(OLD.continue_use AS BINARY))
 OR NOT(CAST(NEW.liked_features_json AS BINARY) <=> CAST(OLD.liked_features_json AS BINARY))
 OR NOT(CAST(NEW.adjustment_preferences_json AS BINARY) <=> CAST(OLD.adjustment_preferences_json AS BINARY))
 OR NOT(CAST(NEW.comment_ciphertext AS BINARY) <=> CAST(OLD.comment_ciphertext AS BINARY))
 OR NOT(CAST(NEW.playback_json AS BINARY) <=> CAST(OLD.playback_json AS BINARY))
 OR NOT(NEW.created_at <=> OLD.created_at)))
 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='immutable feedback authorization or tombstone'; END IF;
END;
CREATE TRIGGER int2_0013_feedback_no_delete BEFORE DELETE ON feedback_v3 FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='feedback idempotency keys must be retained';
CREATE TRIGGER int2_0013_feedback_no_replace BEFORE INSERT ON feedback_v3 FOR EACH ROW
BEGIN
 IF EXISTS(SELECT 1 FROM feedback_v3 WHERE feedback_id=NEW.feedback_id OR (internal_user_pk=NEW.internal_user_pk AND idempotency_key=NEW.idempotency_key))
 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='feedback replacement forbidden'; END IF;
 IF NEW.source_task_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM generation_tasks WHERE task_id=NEW.source_task_id AND internal_user_pk=NEW.internal_user_pk AND music_asset_id=NEW.music_asset_id AND session_row_id=NEW.session_row_id AND status IN ('succeeded','matched_fallback'))
 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='feedback task proof mismatch'; END IF;
END;
CREATE TRIGGER int2_0013_task_proof_immutable BEFORE UPDATE ON generation_tasks FOR EACH ROW
BEGIN
 IF (NOT(NEW.status <=> OLD.status) OR NOT(NEW.session_row_id <=> OLD.session_row_id)) AND EXISTS(SELECT 1 FROM feedback_v3 WHERE source_task_id=OLD.task_id)
 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='referenced task proof immutable'; END IF;
END;
CREATE TRIGGER int2_0013_event_proof_immutable BEFORE UPDATE ON music_playback_events FOR EACH ROW
BEGIN
 IF (NOT(NEW.event_id <=> OLD.event_id) OR NOT(NEW.occurred_at <=> OLD.occurred_at)) AND EXISTS(SELECT 1 FROM feedback_v3 WHERE playback_event_row_id=OLD.playback_event_row_id)
 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='referenced event proof immutable'; END IF;
END;

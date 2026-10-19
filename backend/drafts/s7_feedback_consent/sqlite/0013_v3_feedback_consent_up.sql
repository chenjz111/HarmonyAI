-- UNREGISTERED CANDIDATE. Explicit installer only, after verified 0012.
-- Additive: never rebuild or copy the old feedback/preference tables.
ALTER TABLE feedback_v3 ADD COLUMN consent_policy_version VARCHAR(64) NULL;
ALTER TABLE feedback_v3 ADD COLUMN consented_at DATETIME NULL;
ALTER TABLE feedback_v3 ADD COLUMN deleted_at DATETIME NULL;
ALTER TABLE feedback_v3 ADD COLUMN source_task_id VARCHAR(64) NULL REFERENCES generation_tasks(task_id) ON DELETE RESTRICT;
ALTER TABLE feedback_v3 ADD COLUMN playback_event_row_id INTEGER NULL REFERENCES music_playback_events(playback_event_row_id) ON DELETE RESTRICT;
ALTER TABLE feedback_v3 ADD COLUMN evidence_epoch BIGINT NULL CHECK(evidence_epoch IS NULL OR (typeof(evidence_epoch)='integer' AND evidence_epoch>=0));
ALTER TABLE feedback_v3 ADD COLUMN request_fingerprint VARCHAR(71) NULL CHECK(request_fingerprint IS NULL OR (length(request_fingerprint)=71 AND substr(request_fingerprint,1,7)='sha256:' AND substr(request_fingerprint,8) NOT GLOB '*[^0-9a-f]*'));
ALTER TABLE feedback_v3 ADD COLUMN learning_consent INTEGER NOT NULL DEFAULT 0 CHECK(
 typeof(learning_consent)='integer' AND learning_consent IN (0,1) AND
 ((learning_consent=0 AND consent_policy_version IS NULL AND consented_at IS NULL)
 OR (learning_consent=1 AND consent_policy_version IS NOT NULL AND length(consent_policy_version) BETWEEN 1 AND 64 AND consented_at IS NOT NULL AND evidence_epoch IS NOT NULL AND source_task_id IS NOT NULL AND playback_event_row_id IS NOT NULL AND request_fingerprint IS NOT NULL))
);
ALTER TABLE user_music_preference_versions ADD COLUMN evidence_epoch BIGINT NULL CHECK(evidence_epoch IS NULL OR (typeof(evidence_epoch)='integer' AND evidence_epoch>=0));
CREATE INDEX int2_0013_feedback_owner_deleted ON feedback_v3(internal_user_pk,deleted_at,created_at,feedback_id);
-- Frozen TEXT PRIMARY KEY tables can be nullable in SQLite. Reject existing
-- NULL keys in preflight; protect future writes without rebuilding old tables.
CREATE TRIGGER int2_0013_feedback_nonnull_pk BEFORE INSERT ON feedback_v3
WHEN NEW.feedback_id IS NULL
BEGIN SELECT RAISE(ABORT,'feedback primary key required'); END;
CREATE TRIGGER int2_0013_version_nonnull_pk_insert BEFORE INSERT ON user_music_preference_versions
WHEN NEW.preference_version_id IS NULL
BEGIN SELECT RAISE(ABORT,'preference version primary key required'); END;
CREATE TRIGGER int2_0013_version_nonnull_pk_update BEFORE UPDATE ON user_music_preference_versions
WHEN NEW.preference_version_id IS NULL
BEGIN SELECT RAISE(ABORT,'preference version primary key required'); END;
CREATE TRIGGER int2_0013_feedback_insert_proof BEFORE INSERT ON feedback_v3
WHEN (NEW.source_task_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM generation_tasks t WHERE t.task_id=NEW.source_task_id AND t.internal_user_pk=NEW.internal_user_pk AND t.music_asset_id=NEW.music_asset_id AND t.session_row_id=NEW.session_row_id AND t.status IN ('succeeded','matched_fallback')))
 OR (NEW.playback_event_row_id IS NOT NULL AND (NEW.source_task_id IS NULL OR NOT EXISTS(SELECT 1 FROM music_playback_events e WHERE e.playback_event_row_id=NEW.playback_event_row_id AND e.internal_user_pk=NEW.internal_user_pk AND e.music_asset_id=NEW.music_asset_id AND e.source_context_id=NEW.source_task_id AND e.event_type='play_started')))
BEGIN SELECT RAISE(ABORT,'feedback playback proof mismatch'); END;
CREATE TRIGGER int2_0013_feedback_immutable BEFORE UPDATE ON feedback_v3
WHEN NEW.feedback_id IS NOT OLD.feedback_id OR NEW.internal_user_pk IS NOT OLD.internal_user_pk OR NEW.idempotency_key IS NOT OLD.idempotency_key
 OR NEW.music_asset_id IS NOT OLD.music_asset_id OR NEW.session_row_id IS NOT OLD.session_row_id
 OR NEW.learning_consent IS NOT OLD.learning_consent OR NEW.consent_policy_version IS NOT OLD.consent_policy_version
 OR NEW.consented_at IS NOT OLD.consented_at OR NEW.source_task_id IS NOT OLD.source_task_id
 OR NEW.playback_event_row_id IS NOT OLD.playback_event_row_id OR NEW.evidence_epoch IS NOT OLD.evidence_epoch
 OR NEW.request_fingerprint IS NOT OLD.request_fingerprint OR (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NOT OLD.deleted_at)
 OR (OLD.request_fingerprint IS NOT NULL AND (
 NEW.change_label IS NOT OLD.change_label OR NEW.pre_state_snapshot_json IS NOT OLD.pre_state_snapshot_json
 OR NEW.post_state_json IS NOT OLD.post_state_json OR NEW.experience_json IS NOT OLD.experience_json
 OR NEW.continue_use IS NOT OLD.continue_use OR NEW.liked_features_json IS NOT OLD.liked_features_json
 OR NEW.adjustment_preferences_json IS NOT OLD.adjustment_preferences_json OR NEW.comment_ciphertext IS NOT OLD.comment_ciphertext
 OR NEW.playback_json IS NOT OLD.playback_json OR NEW.created_at IS NOT OLD.created_at))
BEGIN SELECT RAISE(ABORT,'immutable feedback authorization or tombstone'); END;
CREATE TRIGGER int2_0013_feedback_no_delete BEFORE DELETE ON feedback_v3
BEGIN SELECT RAISE(ABORT,'feedback idempotency keys must be retained'); END;
CREATE TRIGGER int2_0013_feedback_no_replace BEFORE INSERT ON feedback_v3
WHEN EXISTS(SELECT 1 FROM feedback_v3 WHERE feedback_id=NEW.feedback_id OR (internal_user_pk=NEW.internal_user_pk AND idempotency_key=NEW.idempotency_key))
BEGIN SELECT RAISE(ABORT,'feedback replacement forbidden'); END;
CREATE TRIGGER int2_0013_task_proof_immutable BEFORE UPDATE ON generation_tasks
WHEN (NEW.task_id IS NOT OLD.task_id OR NEW.internal_user_pk IS NOT OLD.internal_user_pk OR NEW.music_asset_id IS NOT OLD.music_asset_id OR NEW.session_row_id IS NOT OLD.session_row_id OR NEW.status IS NOT OLD.status)
 AND EXISTS(SELECT 1 FROM feedback_v3 WHERE source_task_id=OLD.task_id)
BEGIN SELECT RAISE(ABORT,'referenced task proof immutable'); END;
CREATE TRIGGER int2_0013_event_proof_immutable BEFORE UPDATE ON music_playback_events
WHEN (NEW.playback_event_row_id IS NOT OLD.playback_event_row_id OR NEW.internal_user_pk IS NOT OLD.internal_user_pk OR NEW.event_id IS NOT OLD.event_id OR NEW.music_asset_id IS NOT OLD.music_asset_id OR NEW.source_context_id IS NOT OLD.source_context_id OR NEW.event_type IS NOT OLD.event_type OR NEW.occurred_at IS NOT OLD.occurred_at)
 AND EXISTS(SELECT 1 FROM feedback_v3 WHERE playback_event_row_id=OLD.playback_event_row_id)
BEGIN SELECT RAISE(ABORT,'referenced playback proof immutable'); END;

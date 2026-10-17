-- UNREGISTERED DRAFT: explicit isolated tests only; not a production migration.
CREATE UNIQUE INDEX IF NOT EXISTS uq_s7_task_context_ref ON generation_tasks(task_id,internal_user_pk,music_asset_id);
CREATE TABLE IF NOT EXISTS owner_music_state (
 internal_user_pk INTEGER NOT NULL PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 library_epoch BIGINT NOT NULL DEFAULT 0 CONSTRAINT ck_oms_library_epoch CHECK(library_epoch>=0),
 feedback_evidence_epoch BIGINT NOT NULL DEFAULT 0 CONSTRAINT ck_oms_feedback_epoch CHECK(feedback_evidence_epoch>=0),
 preference_clear_cutoff DATETIME NULL
);
CREATE TABLE IF NOT EXISTS music_library_state (
 internal_user_pk INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 music_asset_id VARCHAR(64) NOT NULL REFERENCES music_assets(music_asset_id),
 user_title VARCHAR(255) NULL,
 last_played_at DATETIME NULL,
 metadata_version BIGINT NOT NULL DEFAULT 0 CONSTRAINT ck_mls_metadata_version CHECK(metadata_version>=0),
 PRIMARY KEY(internal_user_pk,music_asset_id)
);
CREATE INDEX IF NOT EXISTS ix_mls_owner_played ON music_library_state(internal_user_pk,last_played_at,music_asset_id);
CREATE TABLE IF NOT EXISTS music_playback_events (
 internal_user_pk INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 event_id VARCHAR(128) NOT NULL CONSTRAINT ck_mpe_event_id CHECK(length(event_id) BETWEEN 1 AND 128),
 music_asset_id VARCHAR(64) NOT NULL REFERENCES music_assets(music_asset_id),
 origin_task_id VARCHAR(64) NULL,
 event_type VARCHAR(16) NOT NULL DEFAULT 'play_started' CONSTRAINT ck_mpe_event_type CHECK(event_type='play_started'),
 played_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(internal_user_pk,event_id),
 CONSTRAINT fk_mpe_owner_asset_context FOREIGN KEY(origin_task_id,internal_user_pk,music_asset_id) REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id)
);
CREATE INDEX IF NOT EXISTS ix_mpe_owner_asset_played ON music_playback_events(internal_user_pk,music_asset_id,played_at);

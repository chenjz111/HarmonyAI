-- Isolated integration candidate only. Requires actual 0011 before registration.
CREATE UNIQUE INDEX IF NOT EXISTS uq_generation_tasks_owner_asset_context ON generation_tasks(task_id,internal_user_pk,music_asset_id);
CREATE TABLE IF NOT EXISTS owner_music_state (
 owner_internal_user_pk INTEGER NOT NULL PRIMARY KEY,
 library_epoch BIGINT NOT NULL DEFAULT 0 CHECK(library_epoch>=0),
 feedback_evidence_epoch BIGINT NOT NULL DEFAULT 0 CHECK(feedback_evidence_epoch>=0),
 preference_clear_cutoff DATETIME NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS music_library_state (
 owner_internal_user_pk INTEGER NOT NULL,
 music_asset_id VARCHAR(64) NOT NULL,
 user_title VARCHAR(120) NULL CHECK(user_title IS NULL OR (length(user_title)>=1 AND length(user_title)<=120)),
 metadata_version BIGINT NOT NULL DEFAULT 0 CHECK(metadata_version>=0),
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(owner_internal_user_pk,music_asset_id),
 FOREIGN KEY(owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS music_playback_events (
 playback_event_row_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
 internal_user_pk INTEGER NOT NULL,
 event_id VARCHAR(64) NOT NULL CHECK(length(event_id)>=1 AND length(event_id)<=64),
 music_asset_id VARCHAR(64) NOT NULL,
 event_type VARCHAR(24) NOT NULL CHECK(event_type IN ('play_started')),
 source_context_id VARCHAR(64) NULL CHECK(source_context_id IS NULL OR length(source_context_id)<=64),
 occurred_at DATETIME NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_music_playback_events_owner_event UNIQUE(internal_user_pk,event_id),
 FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id) ON DELETE CASCADE,
 CONSTRAINT fk_playback_owner_asset_context FOREIGN KEY(source_context_id,internal_user_pk,music_asset_id) REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id)
);
CREATE INDEX IF NOT EXISTS ix_music_playback_events_internal_user_pk ON music_playback_events(internal_user_pk);
CREATE INDEX IF NOT EXISTS ix_music_playback_events_music_asset_id ON music_playback_events(music_asset_id);

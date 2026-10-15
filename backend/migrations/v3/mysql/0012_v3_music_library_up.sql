-- Candidate; MySQL >=8.0.16; implicit DDL commits require operator recovery.
CREATE UNIQUE INDEX uq_generation_tasks_owner_asset_context ON generation_tasks(task_id,internal_user_pk,music_asset_id);
CREATE TABLE IF NOT EXISTS owner_music_state (
 owner_internal_user_pk INT NOT NULL PRIMARY KEY,
 library_epoch BIGINT NOT NULL DEFAULT 0 CHECK(library_epoch>=0),
 feedback_evidence_epoch BIGINT NOT NULL DEFAULT 0 CHECK(feedback_evidence_epoch>=0),
 preference_clear_cutoff DATETIME(6) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_oms_owner FOREIGN KEY(owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS music_library_state (
 owner_internal_user_pk INT NOT NULL,
 music_asset_id VARCHAR(64) NOT NULL,
 user_title VARCHAR(120) NULL CHECK(user_title IS NULL OR (CHAR_LENGTH(user_title)>=1 AND CHAR_LENGTH(user_title)<=120)),
 metadata_version BIGINT NOT NULL DEFAULT 0 CHECK(metadata_version>=0),
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 PRIMARY KEY(owner_internal_user_pk,music_asset_id),
 CONSTRAINT fk_mls_owner FOREIGN KEY(owner_internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_mls_asset FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS music_playback_events (
 playback_event_row_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 internal_user_pk INT NOT NULL,
 event_id VARCHAR(64) NOT NULL CHECK(CHAR_LENGTH(event_id)>=1 AND CHAR_LENGTH(event_id)<=64),
 music_asset_id VARCHAR(64) NOT NULL,
 event_type VARCHAR(24) NOT NULL CHECK(event_type IN ('play_started')),
 source_context_id VARCHAR(64) NULL CHECK(source_context_id IS NULL OR CHAR_LENGTH(source_context_id)<=64),
 occurred_at DATETIME(6) NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT uq_music_playback_events_owner_event UNIQUE(internal_user_pk,event_id),
 CONSTRAINT fk_mpe_owner FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_mpe_asset FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id) ON DELETE CASCADE,
 CONSTRAINT fk_playback_owner_asset_context FOREIGN KEY(source_context_id,internal_user_pk,music_asset_id) REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id),
 INDEX ix_music_playback_events_internal_user_pk(internal_user_pk),
 INDEX ix_music_playback_events_music_asset_id(music_asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- UNREGISTERED DRAFT; MySQL >=8.0.16. DDL auto-commits: no atomic rollback claim.
CREATE UNIQUE INDEX uq_s7_task_context_ref ON generation_tasks(task_id,internal_user_pk,music_asset_id);
CREATE TABLE owner_music_state (
 internal_user_pk INT NOT NULL PRIMARY KEY,
 library_epoch BIGINT NOT NULL DEFAULT 0,
 feedback_evidence_epoch BIGINT NOT NULL DEFAULT 0,
 preference_clear_cutoff DATETIME(6) NULL,
 CONSTRAINT fk_oms_owner FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT ck_oms_library_epoch CHECK(library_epoch>=0),
 CONSTRAINT ck_oms_feedback_epoch CHECK(feedback_evidence_epoch>=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE music_library_state (
 internal_user_pk INT NOT NULL,
 music_asset_id VARCHAR(64) NOT NULL,
 user_title VARCHAR(255) NULL,
 last_played_at DATETIME(6) NULL,
 metadata_version BIGINT NOT NULL DEFAULT 0,
 PRIMARY KEY(internal_user_pk,music_asset_id),
 CONSTRAINT fk_mls_owner FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_mls_asset FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id),
 CONSTRAINT ck_mls_metadata_version CHECK(metadata_version>=0),
 INDEX ix_mls_owner_played(internal_user_pk,last_played_at,music_asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE music_playback_events (
 internal_user_pk INT NOT NULL,
 event_id VARCHAR(128) NOT NULL,
 music_asset_id VARCHAR(64) NOT NULL,
 origin_task_id VARCHAR(64) NULL,
 event_type VARCHAR(16) NOT NULL DEFAULT 'play_started',
 played_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 PRIMARY KEY(internal_user_pk,event_id),
 CONSTRAINT fk_mpe_owner FOREIGN KEY(internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_mpe_asset FOREIGN KEY(music_asset_id) REFERENCES music_assets(music_asset_id),
 CONSTRAINT fk_mpe_owner_asset_context FOREIGN KEY(origin_task_id,internal_user_pk,music_asset_id) REFERENCES generation_tasks(task_id,internal_user_pk,music_asset_id),
 CONSTRAINT ck_mpe_event_type CHECK(event_type='play_started'),
 CONSTRAINT ck_mpe_event_id CHECK(length(event_id) BETWEEN 1 AND 128),
 INDEX ix_mpe_owner_asset_played(internal_user_pk,music_asset_id,played_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

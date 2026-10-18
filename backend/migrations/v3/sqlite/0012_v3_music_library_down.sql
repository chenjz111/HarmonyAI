-- Caller owns transaction. Refuse extension data and later migrations.
CREATE TEMP TABLE library_0012_down_guard(ok INTEGER NOT NULL CHECK(ok=1));
INSERT INTO library_0012_down_guard SELECT CASE WHEN
 (SELECT count(*) FROM owner_music_state)=0 AND
 (SELECT count(*) FROM music_library_state)=0 AND
 (SELECT count(*) FROM music_playback_events)=0 AND
 (SELECT count(*) FROM schema_migrations WHERE version>'0012_v3_music_library')=0
 THEN 1 ELSE 0 END;
DROP TABLE library_0012_down_guard;
DROP TABLE music_playback_events;
DROP TABLE music_library_state;
DROP TABLE owner_music_state;
DROP INDEX uq_generation_tasks_owner_asset_context;
DELETE FROM schema_migrations WHERE version='0012_v3_music_library';

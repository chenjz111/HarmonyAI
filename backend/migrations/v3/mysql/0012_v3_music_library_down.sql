-- Requires preflight: all 3 extension tables empty, no later version, backup.
-- NOT an atomic rollback; real MySQL recovery remains NOT RUN.
DROP TABLE music_playback_events;
DROP TABLE music_library_state;
DROP TABLE owner_music_state;
DROP INDEX uq_generation_tasks_owner_asset_context ON generation_tasks;
DELETE FROM schema_migrations WHERE version='0012_v3_music_library';

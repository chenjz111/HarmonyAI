-- UNREGISTERED DRAFT. Preflight must refuse nonempty side state/events.
DROP TABLE music_playback_events;
DROP TABLE music_library_state;
DROP TABLE owner_music_state;
DROP INDEX uq_s7_task_context_ref ON generation_tasks;

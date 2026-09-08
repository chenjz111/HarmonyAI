ALTER TABLE diagnosis_runs
    DROP COLUMN preference_version,
    DROP COLUMN preference_profile_id,
    DROP COLUMN five_tone_generated_at,
    DROP COLUMN five_tone_read_model_checksum,
    DROP COLUMN five_tone_read_model_json,
    DROP COLUMN five_tone_read_model_schema_version;

DELETE FROM schema_migrations WHERE version = '0009_v3_five_tone_read_model';

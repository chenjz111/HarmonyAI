-- Persist the validated PUBLIC Five-Tone Analysis read model as an immutable
-- diagnosis snapshot. Nullable columns preserve historical Diagnosis rows.
ALTER TABLE diagnosis_runs
    ADD COLUMN five_tone_read_model_schema_version VARCHAR(64) NULL,
    ADD COLUMN five_tone_read_model_json JSON NULL,
    ADD COLUMN five_tone_read_model_checksum VARCHAR(96) NULL,
    ADD COLUMN generation_spec_json JSON NULL,
    ADD COLUMN five_tone_generated_at DATETIME(6) NULL,
    ADD COLUMN preference_profile_id VARCHAR(64) NULL,
    ADD COLUMN preference_version INTEGER NULL;

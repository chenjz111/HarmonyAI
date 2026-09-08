PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- Persist the validated PUBLIC Five-Tone Analysis read model as an immutable
-- diagnosis snapshot. Nullable columns preserve historical Diagnosis rows.
ALTER TABLE diagnosis_runs ADD COLUMN five_tone_read_model_schema_version TEXT;
ALTER TABLE diagnosis_runs ADD COLUMN five_tone_read_model_json TEXT;
ALTER TABLE diagnosis_runs ADD COLUMN five_tone_read_model_checksum TEXT;
ALTER TABLE diagnosis_runs ADD COLUMN five_tone_generated_at DATETIME;
ALTER TABLE diagnosis_runs ADD COLUMN preference_profile_id TEXT;
ALTER TABLE diagnosis_runs ADD COLUMN preference_version INTEGER;

COMMIT;
PRAGMA foreign_keys=ON;

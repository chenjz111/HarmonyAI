PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

-- 0007_v3_prescription_mode — unify the prescription_mode CHECK with the
-- V3.1-approved four modes.

ALTER TABLE prescription_v3 RENAME TO prescription_v3_old;
CREATE TABLE prescription_v3 (
    prescription_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    diagnosis_id TEXT NOT NULL,
    status TEXT NOT NULL,
    prescription_mode TEXT,
    tone_profile_json TEXT,
    generation_spec_json TEXT,
    preference_profile_id TEXT,
    preference_version_id TEXT,
    personalization_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_runs(diagnosis_id),
    CHECK (status IN ('success', 'degraded', 'withheld')),
    CHECK (
        prescription_mode IS NULL OR prescription_mode IN
        ('syndrome_based', 'candidate_blend', 'emotion_based', 'wellness')
    ),
    CHECK (
        (status = 'withheld' AND generation_spec_json IS NULL)
        OR (status IN ('success', 'degraded') AND generation_spec_json IS NOT NULL)
    )
);
INSERT INTO prescription_v3 (
    prescription_id, internal_user_pk, session_row_id, diagnosis_id, status,
    prescription_mode, tone_profile_json, generation_spec_json,
    preference_profile_id, preference_version_id, personalization_json,
    presentation_json, created_at
)
SELECT
    prescription_id, internal_user_pk, session_row_id, diagnosis_id, status,
    prescription_mode, tone_profile_json, generation_spec_json,
    preference_profile_id, preference_version_id, personalization_json,
    presentation_json, created_at
FROM prescription_v3_old;
DROP TABLE prescription_v3_old;
CREATE INDEX IF NOT EXISTS ix_prescription_v3_user_created
    ON prescription_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_prescription_v3_diagnosis
    ON prescription_v3(diagnosis_id);

COMMIT;
PRAGMA foreign_keys=ON;

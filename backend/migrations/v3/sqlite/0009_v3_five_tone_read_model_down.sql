PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

ALTER TABLE diagnosis_runs RENAME TO diagnosis_runs_old;
CREATE TABLE diagnosis_runs (
    diagnosis_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    assessment_id TEXT NOT NULL,
    assessment_revision INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'running', 'success', 'degraded', 'abstained', 'withheld', 'failed'
    )),
    abstained INTEGER NOT NULL CHECK (abstained IN (0, 1)),
    abstain_reason TEXT,
    primary_tendency_id TEXT,
    element_profile_json TEXT,
    degradation_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    provider_run_id TEXT,
    rag_run_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (assessment_id, assessment_revision)
        REFERENCES assessment_revisions_v3(assessment_id, revision),
    CHECK ((abstained = 1) OR (abstain_reason IS NULL)),
    UNIQUE (assessment_id, assessment_revision, diagnosis_id)
);
INSERT INTO diagnosis_runs (
    diagnosis_id, internal_user_pk, session_row_id, assessment_id,
    assessment_revision, status, abstained, abstain_reason,
    primary_tendency_id, element_profile_json, degradation_json,
    presentation_json, provider_run_id, rag_run_id, created_at, updated_at
)
SELECT
    diagnosis_id, internal_user_pk, session_row_id, assessment_id,
    assessment_revision, status, abstained, abstain_reason,
    primary_tendency_id, element_profile_json, degradation_json,
    presentation_json, provider_run_id, rag_run_id, created_at, updated_at
FROM diagnosis_runs_old;
DROP TABLE diagnosis_runs_old;
CREATE INDEX IF NOT EXISTS ix_diagnosis_runs_session_created
    ON diagnosis_runs(session_row_id, created_at);
CREATE INDEX IF NOT EXISTS ix_diagnosis_runs_status
    ON diagnosis_runs(status);

DELETE FROM schema_migrations WHERE version = '0009_v3_five_tone_read_model';
COMMIT;
PRAGMA foreign_keys=ON;

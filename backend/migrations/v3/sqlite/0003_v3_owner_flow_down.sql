PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

-- 0003_v3_owner_flow rollback — reverse dependency order.

DROP TABLE IF EXISTS session_input_revisions;

ALTER TABLE assessment_revisions_v3 RENAME TO assessment_revisions_v3_revert;
CREATE TABLE assessment_revisions_v3 (
    assessment_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    previous_revision INTEGER,
    understanding_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    confirmation_status TEXT NOT NULL,
    state_summary TEXT NOT NULL,
    recent_context_summary TEXT,
    organ_profile_json TEXT NOT NULL,
    evidence_coverage REAL NOT NULL,
    source_diversity INTEGER NOT NULL,
    conflicts_json TEXT NOT NULL,
    missing_information_json TEXT NOT NULL,
    degradation_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    confirmed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (assessment_id, revision),
    FOREIGN KEY (assessment_id) REFERENCES assessment_v3(assessment_id) ON DELETE CASCADE,
    CHECK (revision >= 1),
    CHECK (evidence_coverage >= 0 AND evidence_coverage <= 1),
    CHECK (source_diversity >= 0),
    CHECK (
        (confirmed_at IS NULL) OR (confirmation_status = 'confirmed')
    )
);
INSERT INTO assessment_revisions_v3 (
    assessment_id, revision, previous_revision, understanding_revision,
    status, confirmation_status, state_summary, recent_context_summary,
    organ_profile_json, evidence_coverage, source_diversity,
    conflicts_json, missing_information_json, degradation_json,
    presentation_json, confirmed_at, created_at
)
SELECT
    assessment_id, revision, previous_revision, understanding_revision,
    status, confirmation_status, state_summary, recent_context_summary,
    organ_profile_json, evidence_coverage, source_diversity,
    conflicts_json, missing_information_json, degradation_json,
    presentation_json, confirmed_at, created_at
FROM assessment_revisions_v3_revert;
DROP TABLE assessment_revisions_v3_revert;

ALTER TABLE assessment_v3 RENAME TO assessment_v3_revert;
CREATE TABLE assessment_v3 (
    assessment_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    understanding_id TEXT NOT NULL,
    understanding_revision INTEGER NOT NULL,
    questionnaire_submission_id TEXT,
    current_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    safety_status TEXT NOT NULL,
    user_goal_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (understanding_id, understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    FOREIGN KEY (questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    UNIQUE (session_row_id, assessment_id),
    CHECK (current_revision >= 1),
    CHECK (status IN ('needs_confirmation', 'confirmed', 'degraded', 'withheld'))
);
INSERT INTO assessment_v3 (
    assessment_id, internal_user_pk, session_row_id,
    understanding_id, understanding_revision, questionnaire_submission_id,
    current_revision, status, safety_status, user_goal_json,
    created_at, updated_at
)
SELECT
    assessment_id, internal_user_pk, session_row_id,
    understanding_id, understanding_revision, questionnaire_submission_id,
    current_revision, status, safety_status, user_goal_json,
    created_at, updated_at
FROM assessment_v3_revert;
DROP TABLE assessment_v3_revert;
CREATE INDEX IF NOT EXISTS ix_assessment_v3_user_created
    ON assessment_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_assessment_v3_session_status
    ON assessment_v3(session_row_id, status);

ALTER TABLE understanding_runs RENAME TO understanding_runs_revert;
CREATE TABLE understanding_runs (
    understanding_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    current_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    safety_status TEXT NOT NULL,
    degradation_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    UNIQUE (understanding_id, internal_user_pk),
    CHECK (current_revision >= 1),
    CHECK (status IN (
        'queued', 'processing', 'needs_confirmation',
        'confirmed', 'degraded', 'failed'
    ))
);
INSERT INTO understanding_runs (
    understanding_id, internal_user_pk, session_row_id,
    current_revision, status, safety_status, degradation_json,
    created_at, updated_at
)
SELECT
    understanding_id, internal_user_pk, session_row_id,
    current_revision, status, safety_status, degradation_json,
    created_at, updated_at
FROM understanding_runs_revert;
DROP TABLE understanding_runs_revert;
CREATE INDEX IF NOT EXISTS ix_understanding_runs_session
    ON understanding_runs(session_row_id);
CREATE INDEX IF NOT EXISTS ix_understanding_runs_user_status
    ON understanding_runs(internal_user_pk, status);

ALTER TABLE sessions DROP COLUMN active_questionnaire_submission_id;
ALTER TABLE sessions DROP COLUMN active_understanding_revision;
ALTER TABLE sessions DROP COLUMN active_understanding_id;
ALTER TABLE sessions DROP COLUMN active_document_id;
ALTER TABLE sessions DROP COLUMN safety_policy;
ALTER TABLE sessions DROP COLUMN input_revision;
ALTER TABLE sessions DROP COLUMN flow_contract_version;

DELETE FROM schema_migrations WHERE version = '0003_v3_owner_flow';
COMMIT;
PRAGMA foreign_keys=ON;

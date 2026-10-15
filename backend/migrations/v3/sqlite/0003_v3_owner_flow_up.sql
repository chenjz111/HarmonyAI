PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

-- ============================================================
-- 0003_v3_owner_flow — Owner Flow Amendment 001 (SQLite)
-- Mirrors harmonyai-v3-persistence-contract.md §13.
--
--  * Adds session activity columns and the session_input_revisions
--    audit table.
--  * Relaxes NOT NULL on safety_status / user_goal_json /
--    understanding refs so new v3-owner-flow-1 rows may store NULL
--    (deferred_v3 safety, no music goal, pure-questionnaire).
--
-- SQLite cannot ALTER a column's NOT NULL, so the affected tables are
-- rebuilt with the same legacy_alter_table=OFF discipline as 0001:
-- foreign_keys stays OFF during the rebuild so child FKs keep pointing
-- at the original table name.
-- ============================================================

-- ------------------------------------------------------------
-- 13.1 Session activity columns (nullable, service-validated)
-- ------------------------------------------------------------
-- V3_OWNER_FLOW_SESSION_BEGIN
ALTER TABLE sessions ADD COLUMN flow_contract_version VARCHAR(32);
ALTER TABLE sessions ADD COLUMN input_revision INTEGER;
ALTER TABLE sessions ADD COLUMN safety_policy VARCHAR(32);
ALTER TABLE sessions ADD COLUMN active_document_id VARCHAR(64);
ALTER TABLE sessions ADD COLUMN active_understanding_id VARCHAR(64);
ALTER TABLE sessions ADD COLUMN active_understanding_revision INTEGER;
ALTER TABLE sessions ADD COLUMN active_questionnaire_submission_id VARCHAR(64);
-- V3_OWNER_FLOW_SESSION_END

-- ------------------------------------------------------------
-- 13.3 understanding_runs: +flow/policy columns, safety_status NULL
-- ------------------------------------------------------------
ALTER TABLE understanding_runs RENAME TO understanding_runs_owner_flow_old;

CREATE TABLE understanding_runs (
    understanding_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    current_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    safety_status TEXT,
    flow_contract_version TEXT,
    input_revision INTEGER,
    safety_policy TEXT,
    safety_evaluation_status TEXT,
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
    )),
    CHECK (
        flow_contract_version IS NULL OR
        flow_contract_version = 'v3-owner-flow-1'
    ),
    CHECK (input_revision IS NULL OR input_revision >= 1),
    CHECK (safety_policy IS NULL OR safety_policy = 'deferred_v3'),
    CHECK (
        safety_evaluation_status IS NULL OR
        safety_evaluation_status = 'not_run'
    )
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
FROM understanding_runs_owner_flow_old;

DROP TABLE understanding_runs_owner_flow_old;

CREATE INDEX IF NOT EXISTS ix_understanding_runs_session
    ON understanding_runs(session_row_id);
CREATE INDEX IF NOT EXISTS ix_understanding_runs_user_status
    ON understanding_runs(internal_user_pk, status);

-- ------------------------------------------------------------
-- 13.2 assessment_v3: nullable refs/goal/safety + flow columns
-- ------------------------------------------------------------
ALTER TABLE assessment_v3 RENAME TO assessment_v3_owner_flow_old;

CREATE TABLE assessment_v3 (
    assessment_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    understanding_id TEXT,
    understanding_revision INTEGER,
    questionnaire_submission_id TEXT,
    current_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    safety_status TEXT,
    user_goal_json TEXT,
    flow_contract_version TEXT,
    input_revision INTEGER,
    input_mode TEXT,
    safety_policy TEXT,
    safety_evaluation_status TEXT,
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
    CHECK (status IN ('needs_confirmation', 'confirmed', 'degraded', 'withheld')),
    CHECK (
        (understanding_id IS NULL AND understanding_revision IS NULL)
        OR (understanding_id IS NOT NULL AND understanding_revision IS NOT NULL)
    ),
    CHECK (
        input_mode IS NULL OR input_mode IN ('with_document', 'without_document')
    ),
    CHECK (
        flow_contract_version IS NULL OR
        flow_contract_version = 'v3-owner-flow-1'
    ),
    CHECK (input_revision IS NULL OR input_revision >= 1),
    CHECK (safety_policy IS NULL OR safety_policy = 'deferred_v3'),
    CHECK (
        safety_evaluation_status IS NULL OR
        safety_evaluation_status = 'not_run'
    ),
    CHECK (
        flow_contract_version IS NULL OR
        flow_contract_version != 'v3-owner-flow-1' OR user_goal_json IS NULL
    ),
    CHECK (
        flow_contract_version IS NULL OR
        flow_contract_version != 'v3-owner-flow-1' OR safety_status IS NULL
    )
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
FROM assessment_v3_owner_flow_old;

DROP TABLE assessment_v3_owner_flow_old;

CREATE INDEX IF NOT EXISTS ix_assessment_v3_user_created
    ON assessment_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_assessment_v3_session_status
    ON assessment_v3(session_row_id, status);

-- ------------------------------------------------------------
-- 13.2 assessment_revisions_v3: nullable understanding_revision + input_revision
-- ------------------------------------------------------------
ALTER TABLE assessment_revisions_v3 RENAME TO assessment_revisions_v3_owner_flow_old;

CREATE TABLE assessment_revisions_v3 (
    assessment_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    previous_revision INTEGER,
    understanding_revision INTEGER,
    input_revision INTEGER,
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
FROM assessment_revisions_v3_owner_flow_old;

DROP TABLE assessment_revisions_v3_owner_flow_old;

-- ------------------------------------------------------------
-- 13.1 session_input_revisions audit table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_input_revisions (
    session_row_id INTEGER NOT NULL,
    input_revision INTEGER NOT NULL,
    input_mode TEXT,
    active_document_id TEXT,
    active_understanding_id TEXT,
    active_understanding_revision INTEGER,
    active_questionnaire_submission_id TEXT,
    action TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_row_id, input_revision),
    FOREIGN KEY (session_row_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (active_understanding_id, active_understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    FOREIGN KEY (active_questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    CHECK (input_revision >= 1),
    CHECK (
        input_mode IS NULL OR input_mode IN ('with_document', 'without_document')
    ),
    CHECK (
        action IN ('create', 'select_mode', 'replace_document',
            'discard_document', 'confirm_source', 'submit_questionnaire')
    ),
    CHECK (
        (active_understanding_id IS NULL AND active_understanding_revision IS NULL)
        OR (active_understanding_id IS NOT NULL
            AND active_understanding_revision IS NOT NULL)
    )
);

COMMIT;
PRAGMA foreign_keys=ON;

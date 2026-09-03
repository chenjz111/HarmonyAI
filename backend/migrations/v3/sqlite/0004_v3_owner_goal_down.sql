PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

ALTER TABLE assessment_v3 RENAME TO assessment_v3_goal_revert;

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
    flow_contract_version, input_revision, input_mode,
    safety_policy, safety_evaluation_status, created_at, updated_at
)
SELECT
    assessment_id, internal_user_pk, session_row_id,
    understanding_id, understanding_revision, questionnaire_submission_id,
    current_revision, status, safety_status, user_goal_json,
    flow_contract_version, input_revision, input_mode,
    safety_policy, safety_evaluation_status, created_at, updated_at
FROM assessment_v3_goal_revert;

DROP TABLE assessment_v3_goal_revert;
CREATE INDEX IF NOT EXISTS ix_assessment_v3_user_created
    ON assessment_v3(internal_user_pk, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_assessment_v3_session_status
    ON assessment_v3(session_row_id, status);

COMMIT;
PRAGMA foreign_keys=ON;

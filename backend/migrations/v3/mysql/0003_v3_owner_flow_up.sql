-- ============================================================
-- 0003_v3_owner_flow — Owner Flow Amendment 001 (MySQL 8)
-- Mirrors harmonyai-v3-persistence-contract.md §13.
--
-- Adds session activity columns and the session_input_revisions audit
-- table; relaxes NOT NULL on safety_status / user_goal_json /
-- understanding refs so new v3-owner-flow-1 rows may store NULL.
-- ============================================================

-- 13.1 Session activity columns (nullable, service-validated).
-- V3_OWNER_FLOW_SESSION_BEGIN
ALTER TABLE sessions
    ADD COLUMN flow_contract_version VARCHAR(32) NULL,
    ADD COLUMN input_revision INTEGER NULL,
    ADD COLUMN safety_policy VARCHAR(32) NULL,
    ADD COLUMN active_document_id VARCHAR(64) NULL,
    ADD COLUMN active_understanding_id VARCHAR(64) NULL,
    ADD COLUMN active_understanding_revision INTEGER NULL,
    ADD COLUMN active_questionnaire_submission_id VARCHAR(64) NULL;
-- V3_OWNER_FLOW_SESSION_END

-- 13.3 understanding_runs: flow/policy columns + nullable safety_status.
ALTER TABLE understanding_runs
    ADD COLUMN flow_contract_version VARCHAR(32) NULL,
    ADD COLUMN input_revision INTEGER NULL,
    ADD COLUMN safety_policy VARCHAR(32) NULL,
    ADD COLUMN safety_evaluation_status VARCHAR(32) NULL,
    MODIFY COLUMN safety_status VARCHAR(32) NULL;

-- 13.2 assessment_v3: nullable refs/goal/safety + flow columns.
ALTER TABLE assessment_v3
    MODIFY COLUMN understanding_id VARCHAR(64) NULL,
    MODIFY COLUMN understanding_revision INTEGER NULL,
    MODIFY COLUMN safety_status VARCHAR(32) NULL,
    MODIFY COLUMN user_goal_json JSON NULL,
    ADD COLUMN flow_contract_version VARCHAR(32) NULL,
    ADD COLUMN input_revision INTEGER NULL,
    ADD COLUMN input_mode VARCHAR(16) NULL,
    ADD COLUMN safety_policy VARCHAR(32) NULL,
    ADD COLUMN safety_evaluation_status VARCHAR(32) NULL;

-- 13.2 assessment_revisions_v3: nullable understanding_revision + input_revision.
ALTER TABLE assessment_revisions_v3
    MODIFY COLUMN understanding_revision INTEGER NULL,
    ADD COLUMN input_revision INTEGER NULL;

-- 13.1 session_input_revisions audit table.
CREATE TABLE IF NOT EXISTS session_input_revisions (
    session_row_id INTEGER NOT NULL,
    input_revision INTEGER NOT NULL,
    input_mode VARCHAR(16) NULL,
    active_document_id VARCHAR(64) NULL,
    active_understanding_id VARCHAR(64) NULL,
    active_understanding_revision INTEGER NULL,
    active_questionnaire_submission_id VARCHAR(64) NULL,
    action VARCHAR(32) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (session_row_id, input_revision),
    CONSTRAINT fk_session_input_revisions_session
        FOREIGN KEY (session_row_id) REFERENCES sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_session_input_revisions_understanding
        FOREIGN KEY (active_understanding_id, active_understanding_revision)
        REFERENCES understanding_revisions(understanding_id, revision),
    CONSTRAINT fk_session_input_revisions_questionnaire
        FOREIGN KEY (active_questionnaire_submission_id)
        REFERENCES questionnaire_submissions_v3(questionnaire_submission_id),
    CONSTRAINT ck_session_input_revisions_revision
        CHECK (input_revision >= 1),
    CONSTRAINT ck_session_input_revisions_mode
        CHECK (input_mode IS NULL OR input_mode IN ('with_document', 'without_document')),
    CONSTRAINT ck_session_input_revisions_action
        CHECK (action IN ('create', 'select_mode', 'replace_document',
            'discard_document', 'confirm_source', 'submit_questionnaire')),
    CONSTRAINT ck_session_input_revisions_understanding_pair
        CHECK (
            (active_understanding_id IS NULL AND active_understanding_revision IS NULL)
            OR (active_understanding_id IS NOT NULL
                AND active_understanding_revision IS NOT NULL)
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

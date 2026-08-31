-- 0003_v3_owner_flow rollback — reverse dependency order.

DROP TABLE IF EXISTS session_input_revisions;

ALTER TABLE assessment_revisions_v3
    DROP COLUMN input_revision,
    MODIFY COLUMN understanding_revision INTEGER NOT NULL;

ALTER TABLE assessment_v3
    DROP COLUMN safety_evaluation_status,
    DROP COLUMN safety_policy,
    DROP COLUMN input_mode,
    DROP COLUMN input_revision,
    DROP COLUMN flow_contract_version,
    MODIFY COLUMN user_goal_json JSON NOT NULL,
    MODIFY COLUMN safety_status VARCHAR(32) NOT NULL,
    MODIFY COLUMN understanding_revision INTEGER NOT NULL,
    MODIFY COLUMN understanding_id VARCHAR(64) NOT NULL;

ALTER TABLE understanding_runs
    DROP COLUMN safety_evaluation_status,
    DROP COLUMN safety_policy,
    DROP COLUMN input_revision,
    DROP COLUMN flow_contract_version,
    MODIFY COLUMN safety_status VARCHAR(32) NOT NULL;

ALTER TABLE sessions
    DROP COLUMN active_questionnaire_submission_id,
    DROP COLUMN active_understanding_revision,
    DROP COLUMN active_understanding_id,
    DROP COLUMN active_document_id,
    DROP COLUMN safety_policy,
    DROP COLUMN input_revision,
    DROP COLUMN flow_contract_version;

DELETE FROM schema_migrations WHERE version = '0003_v3_owner_flow';

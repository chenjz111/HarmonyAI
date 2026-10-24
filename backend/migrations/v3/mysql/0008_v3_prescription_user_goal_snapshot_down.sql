-- 0008_v3_prescription_user_goal_snapshot rollback.

ALTER TABLE prescription_v3
    DROP COLUMN user_goal_json;

DELETE FROM schema_migrations WHERE version = '0008_v3_prescription_user_goal_snapshot';

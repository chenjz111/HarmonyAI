-- Rollback 0002_v3_session_activity
-- response_json was added to idempotency_records by this migration's up
-- and must be removed here, together with the two new tables

ALTER TABLE idempotency_records DROP COLUMN response_json;

DROP TABLE IF EXISTS v3_understanding_snapshots;
DROP TABLE IF EXISTS v3_session_activities;

PRAGMA foreign_keys=OFF;
PRAGMA legacy_alter_table=ON;
BEGIN IMMEDIATE;

ALTER TABLE generation_tasks RENAME TO generation_tasks_old;
CREATE TABLE generation_tasks (
    task_id TEXT PRIMARY KEY,
    internal_user_pk INTEGER NOT NULL,
    session_row_id INTEGER NOT NULL,
    prescription_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'succeeded', 'matched_fallback', 'failed', 'cancelled'
    )),
    provider TEXT,
    provider_task_id TEXT,
    progress_value INTEGER CHECK (progress_value IS NULL OR (progress_value >= 0 AND progress_value <= 100)),
    progress_indeterminate INTEGER NOT NULL CHECK (progress_indeterminate IN (0, 1)),
    message_code TEXT NOT NULL,
    fallback_applied INTEGER NOT NULL CHECK (fallback_applied IN (0, 1)),
    fallback_reason_code TEXT,
    error_code TEXT,
    music_asset_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (internal_user_pk) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_row_id) REFERENCES sessions(id),
    FOREIGN KEY (prescription_id) REFERENCES prescription_v3(prescription_id),
    FOREIGN KEY (music_asset_id) REFERENCES music_assets(music_asset_id),
    UNIQUE (internal_user_pk, idempotency_key),
    CHECK (
        (status = 'succeeded' AND music_asset_id IS NOT NULL AND fallback_applied = 0)
        OR
        (status = 'matched_fallback' AND music_asset_id IS NOT NULL AND fallback_applied = 1)
        OR
        (status IN ('queued', 'running', 'failed', 'cancelled') AND music_asset_id IS NULL)
    )
);
INSERT INTO generation_tasks (
    task_id, internal_user_pk, session_row_id, prescription_id, idempotency_key,
    status, provider, provider_task_id, progress_value, progress_indeterminate,
    message_code, fallback_applied, fallback_reason_code, error_code,
    music_asset_id, created_at, updated_at, completed_at
)
SELECT
    task_id, internal_user_pk, session_row_id, prescription_id, idempotency_key,
    status, provider, provider_task_id, progress_value, progress_indeterminate,
    message_code, fallback_applied, fallback_reason_code, error_code,
    music_asset_id, created_at, updated_at, completed_at
FROM generation_tasks_old;
DROP TABLE generation_tasks_old;
CREATE INDEX IF NOT EXISTS ix_generation_tasks_status_updated
    ON generation_tasks(status, updated_at);
CREATE INDEX IF NOT EXISTS ix_generation_tasks_prescription
    ON generation_tasks(prescription_id);

DELETE FROM schema_migrations WHERE version = '0010_v3_generation_prompt_audit';
COMMIT;
PRAGMA foreign_keys=ON;

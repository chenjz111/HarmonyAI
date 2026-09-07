-- 0007_v3_prescription_mode rollback.

ALTER TABLE prescription_v3
    DROP CHECK ck_prescription_v3_mode,
    DROP COLUMN user_goal_revision,
    ADD CONSTRAINT ck_prescription_v3_mode CHECK (
        prescription_mode IS NULL OR prescription_mode IN
        ('syndrome_based', 'conservative_fallback')
    );

DELETE FROM schema_migrations WHERE version = '0007_v3_prescription_mode';

-- 0007_v3_prescription_mode — unify the prescription_mode CHECK with the
-- V3.1-approved four modes.

ALTER TABLE prescription_v3
    DROP CHECK ck_prescription_v3_mode,
    ADD CONSTRAINT ck_prescription_v3_mode CHECK (
        prescription_mode IS NULL OR prescription_mode IN
        ('syndrome_based', 'candidate_blend', 'emotion_based', 'wellness')
    );

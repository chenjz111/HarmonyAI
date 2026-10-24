PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;

-- 0008_v3_prescription_user_goal_snapshot — persist a traceable UserGoal
-- content snapshot alongside the prescription (audit only, not in read model).

ALTER TABLE prescription_v3 ADD COLUMN user_goal_json TEXT;

COMMIT;
PRAGMA foreign_keys=ON;

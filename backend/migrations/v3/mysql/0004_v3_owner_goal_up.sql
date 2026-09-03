-- Owner Flow UserGoal is an independent optional personalization input.
-- Remove only the obsolete 0003 no-goal check in an additive migration.
ALTER TABLE assessment_v3
    DROP CHECK ck_assessment_v3_no_goal_new_flow;

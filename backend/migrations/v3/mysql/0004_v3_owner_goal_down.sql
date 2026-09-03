ALTER TABLE assessment_v3
    ADD CONSTRAINT ck_assessment_v3_no_goal_new_flow CHECK (
        flow_contract_version IS NULL OR
        flow_contract_version != 'v3-owner-flow-1' OR user_goal_json IS NULL
    );

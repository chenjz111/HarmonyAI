from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope


def valid_v21_inputs():
    return {
        "assessment_id": "asmt-flow-001",
        "session_id": "session-flow-001",
        "user_id": "user-flow-001",
        "questionnaire_answers": valid_v21_envelope(),
    }


def test_v21_workflow_requires_confirmation_before_diagnosis():
    from backend.ai_engine.real_workflow import run_real_workflow_v21

    result = run_real_workflow_v21(
        **valid_v21_inputs(),
        assessment_confirmed=False,
    )

    assert result["assessment"]["requires_user_confirmation"] is True
    assert result["diagnosis"] is None
    assert result["agent_statuses"]["confirmation"] == "needs_confirmation"

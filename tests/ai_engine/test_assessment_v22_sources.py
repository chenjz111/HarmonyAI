from backend.ai_engine.assessment_v2 import run_assessment_v21
from tests.ai_engine.test_questionnaire_v22 import valid_v22_envelope


def submission(questionnaire=None):
    return {
        "assessment_id": "asmt-v22-source",
        "session_id": "session-v22-source",
        "user_id": "user-v22-source",
        "questionnaire_answers": questionnaire or valid_v22_envelope(),
        "confirmation_status": "pending",
    }


def test_v22_goal_is_preference_evidence_not_symptom_evidence():
    result = run_assessment_v21(submission())
    goal = next(item for item in result["evidence_items"] if item["label"] == "user_goal")
    assert goal["category"] == "goal"
    assert goal["value"]["primary_goal"] == "relaxation"
    assert all(
        item["label"] != "sleep_disturbance" or item["source_ref"] != "questionnaire:q01_user_goal"
        for item in result["evidence_items"]
    )


def test_v22_custom_physical_text_is_preserved_as_questionnaire_evidence():
    result = run_assessment_v21(submission())
    custom = next(item for item in result["evidence_items"] if item["label"] == "physical_signal_text")
    assert custom["category"] == "physical"
    assert custom["value"] == "耳鸣"
    assert custom["source_ref"] == "questionnaire:q16_physical_signals:custom_text"


def test_v22_custom_physical_safety_text_enters_existing_safety_engine():
    questionnaire = valid_v22_envelope()
    next(
        item for item in questionnaire["answers"]
        if item["question_id"] == "q16_physical_signals"
    )["value"] = {"selected": ["other"], "custom_text": "现在有明显呼吸困难"}

    result = run_assessment_v21(submission(questionnaire))
    assert result["status"] == "blocked_safety"
    assert result["safety_status"] == "confirmed_acute_physical_risk"


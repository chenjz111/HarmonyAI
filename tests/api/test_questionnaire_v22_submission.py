import pytest
from pydantic import ValidationError

from backend.app.schemas.assessment_v2 import QuestionnaireV2Submission
from tests.ai_engine.test_questionnaire_v22 import valid_v22_envelope


def test_api_schema_accepts_v22_structured_goal_and_physical_text():
    submission = QuestionnaireV2Submission.model_validate(valid_v22_envelope())
    assert submission.schema_version == "questionnaire_v2.2"
    assert submission.answers[0].value.primary_goal == "relaxation"
    assert submission.answers[15].value.custom_text == "耳鸣"


def test_api_schema_still_rejects_wrong_v22_answer_count():
    payload = valid_v22_envelope()
    payload["answers"] = payload["answers"][:-1]
    with pytest.raises(ValidationError):
        QuestionnaireV2Submission.model_validate(payload)

def test_api_schema_accepts_real_frontend_v22_question_types():
    payload = valid_v22_envelope()
    payload["answers"][0]["type"] = "goal_selection"
    payload["answers"][15]["type"] = "multi_choice"

    submission = QuestionnaireV2Submission.model_validate(payload)

    assert submission.answers[0].type == "goal_selection"
    assert submission.answers[15].type == "multi_choice"

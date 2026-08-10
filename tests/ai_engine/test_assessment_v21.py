import pytest

from backend.ai_engine.providers import MockProvider
from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope


def grounded_provider():
    return MockProvider(
        {
            "items": [
                {
                    "category": "sleep",
                    "label": "sleep_disturbance",
                    "value": 3,
                    "polarity": "present",
                    "time_window": "过去两周",
                    "quote": "最近两周晚上睡不好",
                    "source_ref": "narrative:sentence_1",
                    "extraction_confidence": 0.9,
                    "negated": False,
                }
            ]
        }
    )


def three_source_submission():
    return {
        "assessment_id": "asmt-v21-001",
        "session_id": "session-v21-001",
        "user_id": "user-v21-001",
        "questionnaire_answers": valid_v21_envelope(),
        "narrative_text": "最近两周晚上睡不好。",
        "document_text": "最近两周晚上睡不好。",
        "document_confirmed": True,
        "confirmation_status": "pending",
    }


def test_assessment_calculates_coverage_and_requires_confirmation():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(three_source_submission(), provider=grounded_provider())

    assert result["evidence_coverage_score"] == pytest.approx(2 / 3)
    assert result["requires_user_confirmation"] is True
    assert result["input_processing_status"]["narrative"]["status"] == "processed"
    assert result["input_processing_status"]["document"]["status"] == "confirmed"
    assert all(item["source_type"] for item in result["evidence_items"])


def test_assessment_uses_deterministic_follow_up_priority_and_caps_output():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(
        {
            "assessment_id": "asmt-v21-002",
            "session_id": "session-v21-002",
            "user_id": "user-v21-002",
            "questionnaire_answers": valid_v21_envelope(),
            "confirmation_status": "pending",
        },
        provider=grounded_provider(),
    )

    assert result["status"] == "needs_follow_up"
    assert len(result["follow_up_questions"]) <= 4
    assert result["follow_up_questions"][0]["trigger_reason"] == "supplementary_context"

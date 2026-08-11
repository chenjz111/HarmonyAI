import pytest

from backend.ai_engine.providers import MockProvider
from tests.ai_engine.test_questionnaire_v21 import valid_v21_envelope
from tests.ai_engine.test_questionnaire_v21 import frozen_v21_envelope


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

    assert result["evidence_coverage_score"] == pytest.approx(1.0)
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

    assert result["status"] == "success"
    assert result["follow_up_questions"] == []


def test_questionnaire_only_single_source_is_not_automatically_insufficient():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(
        {
            "assessment_id": "questionnaire-only",
            "session_id": "questionnaire-only-session",
            "user_id": "questionnaire-only-user",
            "questionnaire_answers": valid_v21_envelope(),
            "confirmation_status": "pending",
        }
    )

    assert result["evidence_coverage_score"] == 1.0
    assert result["source_diversity"] == {
        "count": 1,
        "sources": ["questionnaire"],
    }
    assert result["follow_up_questions"] == []


def test_frozen_questionnaire_only_separates_coverage_from_source_diversity():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(
        {
            "assessment_id": "frozen-only",
            "session_id": "frozen-session",
            "user_id": "frozen-user",
            "questionnaire_answers": frozen_v21_envelope(),
            "confirmation_status": "pending",
        }
    )

    assert result["evidence_coverage_score"] == 1.0
    assert result["source_diversity"] == {"count": 1, "sources": ["questionnaire"]}
    assert result["follow_up_questions"] == []
    assert result["requires_user_confirmation"] is True
    assert all(item["category"] in {"emotion", "sleep", "energy", "appetite", "physical", "life_event", "goal"} for item in result["evidence_items"])
    assert all(item["value"] is not None for item in result["evidence_items"])
    assert all(question["max_questions_total"] == 4 for question in result["follow_up_questions"])


def test_user_correction_creates_new_revision_and_user_correction_evidence():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    result = run_assessment_v21(
        {
            "assessment_id": "frozen-revision",
            "session_id": "frozen-session",
            "user_id": "frozen-user",
            "questionnaire_answers": frozen_v21_envelope(),
            "previous_revision": 1,
            "user_correction": [
                {"field": "evidence.tension_worry.value", "value": 2, "from": 1}
            ],
        }
    )

    assert result["revision"] == 2
    assert result["revision_metadata"]["previous_revision"] == 1
    assert result["revision_metadata"]["changes"]
    assert any(item["source_type"] == "user_correction" for item in result["evidence_items"])


def test_frozen_safety_answers_stop_assessment_before_normal_evidence_flow():
    from backend.ai_engine.assessment_v2 import run_assessment_v21

    self_harm = run_assessment_v21(
        {
            "assessment_id": "safety-self-harm",
            "session_id": "safety-session",
            "user_id": "safety-user",
            "questionnaire_answers": frozen_v21_envelope(self_harm="fleeting"),
        }
    )
    emergency = run_assessment_v21(
        {
            "assessment_id": "safety-emergency",
            "session_id": "safety-session",
            "user_id": "safety-user",
            "questionnaire_answers": frozen_v21_envelope(emergency=["confusion"]),
        }
    )

    assert self_harm["status"] == "blocked_safety"
    assert emergency["status"] == "blocked_safety"
    assert "confusion" in emergency["safety_flags"]
    assert self_harm["follow_up_questions"] == []
    assert emergency["follow_up_questions"] == []

from backend.ai_engine.assessment_v2 import run_assessment_v21
import backend.ai_engine.safety_rules as safety_rules
from tests.ai_engine.test_questionnaire_v21 import frozen_v21_envelope


def test_ocr_risk_is_a_pending_signal_not_a_current_high_risk_decision():
    result = safety_rules.evaluate_safety_state(
        confirmed_ocr_text="既往记录中提到自杀想法。",
    )

    assert result["safety_status"] == "needs_verification"
    assert result["requires_safety_verification"] is True
    assert result["personalized_prescription_allowed"] is False
    assert result["comfort_audio_allowed"] is False
    assert result["signals"] == [
        {
            "signal_id": "safety-ocr_document-self_harm_thoughts",
            "type": "self_harm_thoughts",
            "source": "ocr_document",
            "confidence": 0.8,
            "temporal_context": "unknown",
            "subject_context": "unknown",
            "verification_status": "pending",
        }
    ]


def test_direct_questionnaire_self_harm_is_confirmed_mental_health_risk():
    result = safety_rules.evaluate_safety_state(
        questionnaire_safety_flags=["self_harm_thoughts"],
    )

    assert result["safety_status"] == "confirmed_mental_health_risk"
    assert result["requires_safety_verification"] is False
    assert result["personalized_prescription_allowed"] is False
    assert result["comfort_audio_allowed"] is True
    assert result["signals"][0]["source"] == "questionnaire"
    assert result["signals"][0]["verification_status"] == "confirmed"


def test_direct_questionnaire_physical_emergency_takes_priority():
    result = safety_rules.evaluate_safety_state(
        questionnaire_safety_flags=[
            "self_harm_thoughts",
            "severe_breathing_difficulty",
        ],
    )

    assert result["safety_status"] == "confirmed_acute_physical_risk"
    assert result["comfort_audio_allowed"] is False


def test_direct_current_narrative_risk_is_confirmed_not_pending():
    result = safety_rules.evaluate_safety_state(
        narrative_text="我现在正在考虑伤害自己。",
    )

    assert result["safety_status"] == "confirmed_mental_health_risk"
    assert result["signals"][0]["source"] == "user_narrative"
    assert result["signals"][0]["temporal_context"] == "current"


def test_safety_assessment_keeps_questionnaire_evidence_and_real_coverage():
    result = run_assessment_v21(
        {
            "assessment_id": "asmt-safety-evidence",
            "session_id": "session-safety-evidence",
            "user_id": "user-safety-evidence",
            "questionnaire_answers": frozen_v21_envelope(self_harm="fleeting"),
        },
        provider=None,
    )

    assert result["status"] == "blocked_safety"
    assert result["assessment_status"] == "completed"
    assert result["safety_status"] == "confirmed_mental_health_risk"
    assert result["evidence_items"]
    assert result["evidence_coverage_score"] > 0
    assert result["personalized_prescription_allowed"] is False
    assert result["comfort_audio_allowed"] is True


def test_ocr_safety_assessment_requires_dedicated_verification():
    result = run_assessment_v21(
        {
            "assessment_id": "asmt-ocr-safety",
            "session_id": "session-ocr-safety",
            "user_id": "user-ocr-safety",
            "questionnaire_answers": frozen_v21_envelope(),
            "document_text": "记录中提到明确自杀想法。",
            "document_confirmed": True,
        },
        provider=None,
    )

    assert result["status"] == "blocked_safety"
    assert result["safety_status"] == "needs_verification"
    assert result["requires_safety_verification"] is True
    assert result["requires_user_confirmation"] is False
    assert result["evidence_items"]

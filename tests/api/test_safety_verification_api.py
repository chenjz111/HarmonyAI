from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v21 import frozen_v21_envelope


client = TestClient(app)


def _create_ocr_assessment(text="记录中提到明确自杀想法。"):
    suffix = uuid4().hex[:10]
    body = client.post(
        "/api/v2/assessments",
        json={
            "session_id": f"session-verification-{suffix}",
            "user_id": f"user-verification-{suffix}",
            "document_text": text,
            "questionnaire_answers": frozen_v21_envelope(),
        },
    ).json()
    assert body["success"] is True, body
    return body["data"]


def _verify(assessment, resolution):
    response = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/safety-verification",
        json={"revision": assessment["revision"], "resolution": resolution},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True, body
    return body["data"]["assessment"]


@pytest.mark.parametrize(
    "resolution",
    ["past_resolved", "other_person", "ocr_error"],
)
def test_explicit_non_current_ocr_resolutions_clear_the_pending_gate(resolution):
    updated = _verify(_create_ocr_assessment(), resolution)

    assert updated["safety_status"] == "resolved"
    assert updated["requires_safety_verification"] is False
    assert updated["personalized_prescription_allowed"] is True
    assert updated["comfort_audio_allowed"] is False
    assert updated["status"] == "awaiting_confirmation"
    assert updated["requires_user_confirmation"] is True
    assert all(
        signal["verification_status"] == "resolved"
        for signal in updated["safety_signals"]
    )


def test_uncertain_ocr_resolution_keeps_safety_verification_pending():
    updated = _verify(_create_ocr_assessment(), "uncertain")

    assert updated["safety_status"] == "needs_verification"
    assert updated["status"] == "blocked_safety"
    assert updated["requires_safety_verification"] is True
    assert updated["personalized_prescription_allowed"] is False


def test_current_mental_health_risk_enters_support_track_with_comfort_audio():
    updated = _verify(_create_ocr_assessment(), "current")

    assert updated["safety_status"] == "confirmed_mental_health_risk"
    assert updated["status"] == "blocked_safety"
    assert updated["comfort_audio_allowed"] is True
    assert updated["personalized_prescription_allowed"] is False
    assert all(
        signal["verification_status"] == "confirmed"
        for signal in updated["safety_signals"]
    )


def test_current_acute_physical_risk_disallows_comfort_audio():
    updated = _verify(
        _create_ocr_assessment("检查记录中提到持续严重胸痛。"),
        "current",
    )

    assert updated["safety_status"] == "confirmed_acute_physical_risk"
    assert updated["comfort_audio_allowed"] is False
    assert updated["personalized_prescription_allowed"] is False


def test_safety_verification_rejects_assessment_without_pending_signal():
    suffix = uuid4().hex[:10]
    body = client.post(
        "/api/v2/assessments",
        json={
            "session_id": f"session-clear-{suffix}",
            "user_id": f"user-clear-{suffix}",
            "questionnaire_answers": frozen_v21_envelope(),
        },
    ).json()
    assessment = body["data"]

    result = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/safety-verification",
        json={"revision": assessment["revision"], "resolution": "ocr_error"},
    ).json()

    assert result["success"] is False
    assert result["error"]["code"] == "SAFETY_VERIFICATION_NOT_REQUIRED"

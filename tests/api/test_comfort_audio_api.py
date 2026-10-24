from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v21 import frozen_v21_envelope


client = TestClient(app)


def _assessment(document_text: str):
    suffix = uuid4().hex[:10]
    response = client.post(
        "/api/v2/assessments",
        json={
            "session_id": f"comfort-session-{suffix}",
            "user_id": f"comfort-user-{suffix}",
            "document_text": document_text,
            "questionnaire_answers": frozen_v21_envelope(),
        },
    ).json()
    assert response["success"] is True, response
    return response["data"]


def _verify(assessment, resolution="current"):
    response = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/safety-verification",
        json={"revision": assessment["revision"], "resolution": resolution},
    ).json()
    assert response["success"] is True, response
    return response["data"]["assessment"]


def _comfort(assessment, consent=True):
    return client.post(
        f"/api/v2/assessments/{assessment['assessment_id']}/comfort-audio",
        json={"revision": assessment["revision"], "user_initiated": consent},
    ).json()


def test_confirmed_mental_health_risk_can_request_curated_non_prescription_audio():
    assessment = _verify(_assessment("记录中提到明确自杀想法。"))

    body = _comfort(assessment)

    assert body["success"] is True, body
    audio = body["data"]
    assert audio["audio_type"] == "comfort_audio"
    assert audio["source_type"] == "curated_library"
    assert audio["personalized"] is False
    assert audio["is_medical_prescription"] is False
    assert audio["autoplay"] is False
    assert audio["safety_notice_required"] is True
    assert audio["stream_url"].startswith("/static/music/")


def test_comfort_audio_requires_explicit_user_initiation():
    assessment = _verify(_assessment("记录中提到明确自杀想法。"))

    body = _comfort(assessment, consent=False)

    assert body["success"] is False
    assert body["error"]["code"] == "COMFORT_AUDIO_CONSENT_REQUIRED"


def test_acute_physical_risk_never_offers_comfort_audio():
    assessment = _verify(_assessment("检查记录中提到持续严重胸痛。"))

    body = _comfort(assessment)

    assert assessment["safety_status"] == "confirmed_acute_physical_risk"
    assert body["success"] is False
    assert body["error"]["code"] == "COMFORT_AUDIO_NOT_ALLOWED"


def test_pending_or_resolved_safety_does_not_offer_support_track_audio():
    pending = _assessment("记录中提到明确自杀想法。")
    pending_body = _comfort(pending)
    resolved = _verify(pending, "ocr_error")
    resolved_body = _comfort(resolved)

    assert pending_body["success"] is False
    assert pending_body["error"]["code"] == "SAFETY_VERIFICATION_REQUIRED"
    assert resolved_body["success"] is False
    assert resolved_body["error"]["code"] == "COMFORT_AUDIO_NOT_ALLOWED"

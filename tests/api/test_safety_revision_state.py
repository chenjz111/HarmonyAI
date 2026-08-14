from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v21 import frozen_v21_envelope


client = TestClient(app)


def _create_ocr_safety_assessment():
    suffix = uuid4().hex[:10]
    response = client.post(
        "/api/v2/assessments",
        json={
            "session_id": f"session-safety-{suffix}",
            "user_id": f"user-safety-{suffix}",
            "document_text": "记录中提到明确自杀想法。",
            "questionnaire_answers": frozen_v21_envelope(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True, body
    return body["data"]


def test_generic_fully_accurate_confirmation_cannot_clear_pending_safety():
    assessment = _create_ocr_safety_assessment()

    body = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/confirmation",
        json={
            "revision": assessment["revision"],
            "confirmation_level": "fully_accurate",
            "corrections": [],
        },
    ).json()

    updated = body["data"]["assessment"]
    assert updated["status"] == "blocked_safety"
    assert updated["safety_status"] == "needs_verification"
    assert updated["requires_safety_verification"] is True
    assert updated["confirmation_status"] == "fully_accurate"


def test_generic_correction_cannot_clear_pending_safety():
    assessment = _create_ocr_safety_assessment()

    body = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/confirmation",
        json={
            "revision": assessment["revision"],
            "confirmation_level": "partially_accurate",
            "corrections": [
                {"field": "assessment_summary", "from": None, "to": "需要修正"}
            ],
        },
    ).json()

    updated = body["data"]["assessment"]
    assert updated["status"] == "blocked_safety"
    assert updated["safety_status"] == "needs_verification"
    assert updated["requires_safety_verification"] is True

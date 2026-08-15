from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v21 import frozen_v21_envelope


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create(client, *, questionnaire=None, document_text=None):
    suffix = uuid4().hex[:10]
    payload = {
        "session_id": f"dual-e2e-session-{suffix}",
        "user_id": f"dual-e2e-user-{suffix}",
        "questionnaire_answers": questionnaire or frozen_v21_envelope(),
    }
    if document_text is not None:
        payload["document_text"] = document_text
    body = client.post("/api/v2/assessments", json=payload).json()
    assert body["success"] is True, body
    return payload, body["data"]


def _patch(client, assessment, path, payload):
    body = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/{path}",
        json={"revision": assessment["revision"], **payload},
    ).json()
    assert body["success"] is True, body
    return body["data"]["assessment"]


def _confirm(client, assessment):
    return _patch(
        client,
        assessment,
        "confirmation",
        {"confirmation_level": "fully_accurate", "corrections": []},
    )


def _workflow(client, payload, assessment):
    body = client.post(
        "/api/v2/workflows",
        json={
            **payload,
            "assessment_confirmed": True,
            "assessment_id": assessment["assessment_id"],
            "assessment_revision": assessment["revision"],
        },
    ).json()
    assert body["success"] is True, body
    return body["data"]


def test_normal_questionnaire_reaches_authoritative_music(client):
    payload, assessment = _create(client)
    confirmed = _confirm(client, assessment)
    workflow = _workflow(client, payload, confirmed)

    assert confirmed["safety_status"] == "clear"
    assert workflow["confirmation"]["status"] == "confirmed"
    assert workflow["prescription"]["generation_mode"] == "matched"
    assert workflow["music"]["stream_url"].startswith("/static/music/")


def test_historical_ocr_risk_is_verified_then_returns_to_normal_music(client):
    payload, assessment = _create(client, document_text="历史记录提到明确自杀想法。")
    assert assessment["safety_status"] == "needs_verification"
    assert assessment["evidence_items"]
    coverage_before = assessment["evidence_coverage_score"]

    resolved = _patch(
        client, assessment, "safety-verification", {"resolution": "past_resolved"}
    )
    confirmed = _confirm(client, resolved)
    workflow = _workflow(client, payload, confirmed)

    assert resolved["safety_status"] == "resolved"
    assert resolved["evidence_items"] == assessment["evidence_items"]
    assert resolved["evidence_coverage_score"] == coverage_before
    assert workflow["music"] is not None


def test_ocr_false_positive_can_be_resolved_without_erasing_evidence(client):
    payload, assessment = _create(client, document_text="材料中提到持续严重胸痛。")
    resolved = _patch(
        client, assessment, "safety-verification", {"resolution": "ocr_error"}
    )
    confirmed = _confirm(client, resolved)

    assert resolved["safety_status"] == "resolved"
    assert resolved["evidence_items"]
    assert _workflow(client, payload, confirmed)["music"] is not None


def test_direct_q19_current_risk_never_reaches_personalized_music(client):
    _, assessment = _create(
        client, questionnaire=frozen_v21_envelope(self_harm="fleeting")
    )
    confirmation = client.patch(
        f"/api/v2/assessments/{assessment['assessment_id']}/confirmation",
        json={
            "revision": assessment["revision"],
            "confirmation_level": "fully_accurate",
            "corrections": [],
        },
    ).json()

    assert assessment["safety_status"] == "confirmed_mental_health_risk"
    assert assessment["personalized_prescription_allowed"] is False
    assert assessment["comfort_audio_allowed"] is True
    assert confirmation["data"]["assessment"]["status"] == "blocked_safety"


def test_direct_q20_acute_risk_is_emergency_first_without_comfort_audio(client):
    _, assessment = _create(
        client,
        questionnaire=frozen_v21_envelope(emergency=["severe_chest_pain"]),
    )
    comfort = client.post(
        f"/api/v2/assessments/{assessment['assessment_id']}/comfort-audio",
        json={"revision": assessment["revision"], "user_initiated": True},
    ).json()

    assert assessment["safety_status"] == "confirmed_acute_physical_risk"
    assert assessment["comfort_audio_allowed"] is False
    assert comfort["success"] is False
    assert comfort["error"]["code"] == "COMFORT_AUDIO_NOT_ALLOWED"

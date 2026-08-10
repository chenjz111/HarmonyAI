"""HTTP contract tests for the Sprint 3 V2 workflow APIs."""

from fastapi.testclient import TestClient

from backend.app.main import app
from tests.api.test_assessment_v2_schema import questionnaire_envelope


client = TestClient(app)


def _assessment_payload(**overrides):
    payload = {
        "session_id": "sess_http_assessment",
        "user_id": "u_001",
        "document_id": None,
        "document_text": None,
        "narrative_text": None,
        "questionnaire_answers": questionnaire_envelope(),
    }
    payload.update(overrides)
    return payload


def test_v2_workflow_routes_are_registered():
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v2/assessments" in paths
    assert "/api/v2/workflows" in paths
    assert "/api/v2/music" in paths
    assert "/api/v2/sessions/{session_id}" in paths


def test_assessment_endpoint_degrades_to_questionnaire_without_qwen(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )

    response = client.post("/api/v2/assessments", json=_assessment_payload())
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["agent_id"] == "assessment_agent"
    assert body["data"]["status"] == "degraded"
    assert body["data"]["analysis_mode"] == "questionnaire_only"
    assert body["data"]["confidence"] == 0.5


def test_assessment_endpoint_blocks_safety_before_qwen(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )
    payload = _assessment_payload()
    for answer in payload["questionnaire_answers"]["answers"]:
        if answer["question_id"] == "q12_physical_safety":
            answer["value"] = ["self_harm_thoughts"]

    body = client.post("/api/v2/assessments", json=payload).json()

    assert body["success"] is True
    assert body["data"]["status"] == "blocked_safety"
    assert body["data"]["safety_flags"] == ["self_harm_thoughts"]


def test_workflow_endpoint_completes_offline_with_local_music(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )
    session = client.post(
        "/api/v2/sessions",
        json={"user_id": "demo_user_001"},
    ).json()["data"]
    payload = _assessment_payload(
        session_id=session["session_id"],
        assessment_confirmed=True,
    )

    body = client.post("/api/v2/workflows", json=payload).json()

    assert body["success"] is True
    assert body["data"]["assessment"]["status"] == "degraded"
    assert body["data"]["diagnosis"]["status"] == "success"
    assert body["data"]["prescription"]["status"] == "success"
    assert body["data"]["music"]["status"] == "success"
    assert body["data"]["music"]["source_type"] == "matched"
    assert body["data"]["music"]["stream_url"] == "/static/music/jiao-demo.wav"

    session_body = client.get(
        f"/api/v2/sessions/{session['session_id']}"
    ).json()
    assert session_body["success"] is True
    assert session_body["data"]["workflow_result_id"] == body["data"]["result_id"]
    assert session_body["data"]["music_id"] == "music_jiao_001"


def test_workflow_endpoint_stops_until_assessment_is_confirmed(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )
    payload = _assessment_payload(assessment_confirmed=False)

    body = client.post("/api/v2/workflows", json=payload).json()

    assert body["success"] is True
    assert body["data"]["confirmation"] == {"status": "needs_confirmation"}
    assert body["data"]["agent_statuses"]["diagnosis"] == "not_run"
    assert body["data"]["agent_statuses"]["music"] == "not_run"


def test_workflow_endpoint_blocks_music_for_safety_risk(monkeypatch):
    monkeypatch.setattr(
        "backend.ai_engine.assessment_v2.qwen_provider_from_env",
        lambda: None,
    )
    payload = _assessment_payload(assessment_confirmed=True)
    for answer in payload["questionnaire_answers"]["answers"]:
        if answer["question_id"] == "q12_physical_safety":
            answer["value"] = ["severe_chest_pain"]

    body = client.post("/api/v2/workflows", json=payload).json()

    assert body["success"] is True
    assert body["data"]["assessment"]["status"] == "blocked_safety"
    assert body["data"]["confirmation"] == {"status": "blocked_safety"}
    assert body["data"]["agent_statuses"]["diagnosis"] == "not_run"
    assert body["data"]["agent_statuses"]["prescription"] == "not_run"
    assert body["data"]["agent_statuses"]["music"] == "not_run"

def test_music_endpoint_returns_actual_local_catalog_metadata():
    payload = {
        "session_id": "sess_music_http",
        "prescription": {
            "status": "success",
            "generation_mode": "matched",
            "music_feature": {
                "tone_id": "jiao",
                "tone_name": "角调",
                "bpm": 68,
                "instruments": ["古琴", "古筝"],
            },
        },
    }

    body = client.post("/api/v2/music", json=payload).json()

    assert body["success"] is True
    assert body["data"]["agent_id"] == "music_agent"
    assert body["data"]["music_id"] == "music_jiao_001"
    assert body["data"]["title"] == "角调·舒心"
    assert body["data"]["source_type"] == "matched"
    assert body["data"]["stream_url"] == "/static/music/jiao-demo.wav"
    assert body["data"]["mode"] == "角调"
    assert body["data"]["bpm"] == 68
    assert body["data"]["duration_seconds"] == 30
    assert body["data"]["instruments"] == ["古琴", "古筝"]


def test_missing_session_query_returns_safe_not_found_error():
    body = client.get("/api/v2/sessions/sess_missing").json()

    assert body["success"] is False
    assert body["error"]["code"] == "SESSION_NOT_FOUND"
    assert "sess_missing" not in body["error"]["message"]

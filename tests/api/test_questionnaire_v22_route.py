import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from tests.ai_engine.test_questionnaire_v22 import valid_v22_envelope


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]
CANONICAL = json.loads(
    (ROOT / "knowledge" / "questionnaire-v2.2.json").read_text(encoding="utf-8")
)


def test_real_frontend_v22_payload_reaches_assessment_agent(monkeypatch):
    monkeypatch.setenv("HARMONYAI_REAL_AGENTS", "false")
    questionnaire = valid_v22_envelope()
    type_by_id = {
        question["question_id"]: question["type"]
        for question in CANONICAL["questions"]
    }
    for answer in questionnaire["answers"]:
        answer["type"] = type_by_id[answer["question_id"]]

    suffix = uuid4().hex[:10]
    response = client.post(
        "/api/v2/assessments",
        json={
            "session_id": f"session-v22-{suffix}",
            "user_id": f"user-v22-{suffix}",
            "narrative_text": "最近睡前思绪很多，但没有紧急身体不适。",
            "questionnaire_answers": questionnaire,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True, body
    assert body["data"]["input_processing_status"]["questionnaire"]["version"] == "questionnaire_v2.2"
    assert body["data"]["user_goal"]["primary_goal"] == "relaxation"
    assert any(
        item["label"] == "physical_signal_text"
        for item in body["data"]["evidence_items"]
    )

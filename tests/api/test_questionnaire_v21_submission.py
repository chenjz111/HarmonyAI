import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)
QUESTIONNAIRE = json.loads((Path(__file__).parents[2] / "knowledge" / "questionnaire-v2.1.json").read_text(encoding="utf-8"))


def _value(question):
    question_id = question["question_id"]
    if question_id == "q15_appetite_change":
        return {"direction": "decrease", "severity": 2}
    if question_id in {"q16_physical_signals", "q20_emergency"}:
        return ["none"]
    if question_id == "q17_duration":
        return "less_than_3_days"
    if question_id == "q19_self_harm":
        return "never"
    return question["options"][0]["value"]


def _payload():
    return {
        "session_id": "sess_questionnaire_v21",
        "user_id": "user_questionnaire_v21",
        "questionnaire_answers": {
            "schema_version": "questionnaire_v2.1",
            "time_window_days": 14,
            "answers": [{
                "question_id": question["question_id"],
                "value": _value(question),
                "type": question["type"],
            } for question in QUESTIONNAIRE["questions"]],
        },
    }


def test_full_canonical_questionnaire_v21_creates_assessment(monkeypatch):
    monkeypatch.setenv("HARMONYAI_REAL_AGENTS", "false")
    response = client.post("/api/v2/assessments", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["assessment_id"]


def test_questionnaire_v21_requires_twenty_answers_at_api_boundary():
    payload = _payload()
    payload["questionnaire_answers"]["answers"].pop()
    assert client.post("/api/v2/assessments", json=payload).status_code == 422


def test_q15_flat_string_reaches_business_rejection_not_http_422():
    payload = _payload()
    payload["questionnaire_answers"]["answers"][14]["value"] = "decrease"
    response = client.post("/api/v2/assessments", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "ASSESSMENT_INVALID"

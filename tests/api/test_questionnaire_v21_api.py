from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _payload(answer_count):
    return {
        "session_id": "sess_questionnaire_v21",
        "user_id": "user_questionnaire_v21",
        "questionnaire_answers": {
            "schema_version": "questionnaire_v2.1",
            "time_window_days": 14,
            "answers": [
                {
                    "question_id": f"q{index:02d}",
                    "value": 0,
                    "type": "frequency_0_4",
                }
                for index in range(1, answer_count + 1)
            ],
        },
    }


def test_questionnaire_v21_payload_reaches_business_validation_not_http_422():
    response = client.post("/api/v2/assessments", json=_payload(20))
    assert response.status_code == 200
    assert "success" in response.json()


def test_questionnaire_v21_requires_twenty_answers_at_api_boundary():
    response = client.post("/api/v2/assessments", json=_payload(19))
    assert response.status_code == 422

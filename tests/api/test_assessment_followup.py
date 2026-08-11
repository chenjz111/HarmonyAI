from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_follow_up_rejects_legacy_question_creation_payload():
    response = client.post(
        "/api/v2/assessments/not-an-assessment/follow-up",
        json={
            "question": "How long has this continued?",
            "category": "duration",
            "priority": 1,
            "max_questions_total": 4,
        },
    )
    assert response.status_code == 422


def test_follow_up_request_schema_enforces_maximum_four_answers():
    response = client.post(
        "/api/v2/assessments/not-an-assessment/follow-up",
        json={
            "revision": 1,
            "answers": [
                {"follow_up_id": f"fu-{index}", "answer": "answer"}
                for index in range(5)
            ],
        },
    )
    assert response.status_code == 422

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_follow_up_rejects_client_limit_above_four():
    response = client.post(
        "/api/v2/assessments/sess_followup_limit/follow-up",
        json={
            "question": "这些状态持续多久？",
            "category": "duration",
            "priority": 1,
            "max_questions_total": 5,
        },
    )
    assert response.status_code == 422


def test_follow_up_never_creates_more_than_four_for_session():
    for index in range(4):
        response = client.post(
            "/api/v2/assessments/sess_followup_four/follow-up",
            json={
                "question": f"追问 {index + 1}",
                "category": "clarification",
                "priority": index + 1,
                "max_questions_total": 4,
            },
        )
        assert response.json()["success"] is True

    blocked = client.post(
        "/api/v2/assessments/sess_followup_four/follow-up",
        json={
            "question": "第五题",
            "category": "clarification",
            "priority": 1,
            "max_questions_total": 4,
        },
    ).json()
    assert blocked["success"] is False
    assert blocked["error"]["code"] == "MAX_FOLLOWUPS"

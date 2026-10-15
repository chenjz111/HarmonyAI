"""Feedback routes must preserve Sprint 2 while exposing Feedback 2.0."""

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_feedback_openapi_contains_only_canonical_routes():
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/feedback" in paths
    assert "/api/v2/feedback" in paths
    assert "/api/feedback" not in paths
    assert "/api/v1/v2/feedback" not in paths


def test_sprint2_feedback_route_still_works():
    response = client.post(
        "/api/v1/feedback",
        json={
            "user_id": "u_001",
            "session_id": "sess_v1_contract",
            "overall_satisfaction": 4,
        },
    )

    assert response.status_code == 200
    assert response.json()["agent_id"] == "feedback_agent"

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_feedback_route_accepts_change_only_without_default_ratings():
    response = client.post(
        "/api/v2/feedback",
        json={
            "schema_version": "feedback_v2.0",
            "session_id": "session-v22-minimal-route",
            "prescription_id": "prescription-v22-minimal-route",
            "music_id": "music-v22-minimal-route",
            "post_state": {"change_label": "no_change"},
        },
    )

    data = response.json()
    assert data["success"] is True
    assert data["data"]["experience_summary"]["overall_rating"] is None
    assert data["data"]["global_rule_update"] is False

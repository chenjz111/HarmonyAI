from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_assessment_confirmation_appends_revisions_without_overwrite():
    session_id = "sess_revision_history"
    first = client.patch(
        f"/api/v2/assessments/{session_id}/confirmation",
        json={"confirmed": False, "changes": {"primary_state": "紧张"}},
    ).json()
    second = client.patch(
        f"/api/v2/assessments/{session_id}/confirmation",
        json={"confirmed": True, "changes": {"primary_state": "疲惫"}},
    ).json()

    assert first["success"] is True
    assert second["success"] is True
    history = client.get(
        f"/api/v2/assessments/{session_id}/revisions"
    ).json()["data"]["revisions"]
    assert len(history) == 2
    assert {item["new_value"] for item in history} == {"紧张", "疲惫"}
    assert any(item["old_value"] == "紧张" for item in history)

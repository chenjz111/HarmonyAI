from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_confirmation_rejects_legacy_confirmed_changes_payload():
    response = client.patch(
        "/api/v2/assessments/not-an-assessment/confirmation",
        json={"confirmed": True, "changes": {}},
    )
    assert response.status_code == 422


def test_unknown_assessment_has_no_revision_history():
    body = client.get(
        "/api/v2/assessments/not-an-assessment/revisions"
    ).json()
    assert body["success"] is False
    assert body["error"]["code"] == "ASSESSMENT_NOT_FOUND"

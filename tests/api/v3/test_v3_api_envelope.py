from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_guest_auth_uses_v3_success_envelope():
    response = client.post("/api/v3/auth/guest")

    assert response.status_code == 201
    body = response.json()
    assert body["ok"] is True
    assert body["schema_version"] == "harmonyai_v3.0"
    assert body["request_id"].startswith("req_")
    assert body["data"]["token_type"] == "Bearer"
    assert "internal_user_pk" not in body["data"]


def test_v3_errors_use_safe_error_envelope():
    response = client.post(
        "/api/v3/sessions",
        headers={"Idempotency-Key": "missing-auth"},
        json={},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["ok"] is False
    assert body["schema_version"] == "harmonyai_v3.0"
    assert body["request_id"].startswith("req_")
    assert body["error"] == {
        "code": "UNAUTHENTICATED",
        "message": "身份已失效，请重新进入体验。",
        "retryable": False,
        "next_actions": ["restart_guest_session"],
    }
    assert "detail" not in body
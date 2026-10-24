from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def test_guest_auth_creates_distinct_controlled_identities():
    first = client.post("/api/v3/auth/guest")
    second = client.post("/api/v3/auth/guest")

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = _v3_data(first)
    second_body = _v3_data(second)
    assert first_body["token_type"] == "Bearer"
    assert first_body["public_user_id"].startswith("u_guest_")
    assert first_body["public_user_id"] != second_body["public_user_id"]
    assert first_body["access_token"] != second_body["access_token"]
    assert "internal_user_pk" not in first_body


def test_expired_guest_token_is_unauthenticated(monkeypatch):
    monkeypatch.setattr(settings, "JWT_EXPIRE_MINUTES", -1)
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]

    response = client.post(
        "/api/v3/sessions",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "expired-session",
        },
        json={},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
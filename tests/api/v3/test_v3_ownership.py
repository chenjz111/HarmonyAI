from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from backend.app.main import app


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def _guest_headers(*, idempotency_key: str | None = None) -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_session_uses_auth_context_and_ignores_client_user_id():
    headers = _guest_headers(idempotency_key="session-owner-1")
    response = client.post(
        "/api/v3/sessions",
        headers=headers,
        json={"user_id": "u_attacker_supplied"},
    )

    assert response.status_code == 201
    body = _v3_data(response)
    assert body["page"] == "entry"
    assert body["session_id"].startswith("sess_")
    assert "user_id" not in body
    assert "internal_user_pk" not in body


def test_session_creation_is_idempotent_per_authenticated_user():
    headers = _guest_headers(idempotency_key="session-replay-1")
    first = client.post("/api/v3/sessions", headers=headers, json={})
    replay = client.post("/api/v3/sessions", headers=headers, json={})

    assert first.status_code == 201
    assert replay.status_code == 200
    assert _v3_data(replay)["session_id"] == _v3_data(first)["session_id"]


def test_cross_user_session_read_returns_404():
    owner_headers = _guest_headers(idempotency_key="session-private-1")
    session_id = _v3_data(
        client.post("/api/v3/sessions", headers=owner_headers, json={})
    )["session_id"]
    stranger_headers = _guest_headers()

    response = client.get(
        f"/api/v3/sessions/{session_id}",
        headers=stranger_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_session_creation_requires_idempotency_key():
    response = client.post(
        "/api/v3/sessions",
        headers=_guest_headers(),
        json={},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_session_creation_requires_authentication():
    response = client.post(
        "/api/v3/sessions",
        headers={"Idempotency-Key": "missing-auth"},
        json={},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_idempotency_key_is_scoped_per_authenticated_user():
    first = client.post(
        "/api/v3/sessions",
        headers=_guest_headers(idempotency_key="same-key-two-users"),
        json={},
    )
    second = client.post(
        "/api/v3/sessions",
        headers=_guest_headers(idempotency_key="same-key-two-users"),
        json={},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert _v3_data(first)["session_id"] != _v3_data(second)["session_id"]


def test_entry_choice_id_and_route_are_frozen_pairs():
    from backend.app.schemas.v3.session import EntryChoice

    with pytest.raises(ValidationError):
        EntryChoice.model_validate(
            {
                "id": "with_document",
                "label": "我有近期材料",
                "next_route": "/v3/narrative",
            }
        )


def test_owner_flow_entry_skips_narrative_and_goes_to_questionnaire():
    headers = _guest_headers(idempotency_key="owner-entry-questionnaire-1")
    response = client.post(
        "/api/v3/sessions",
        headers=headers,
        json={"flow_contract_version": "v3-owner-flow-1"},
    )

    assert response.status_code == 201
    choices = {choice["id"]: choice["next_route"] for choice in _v3_data(response)["choices"]}
    assert choices["with_document"] == "/v3/material"
    assert choices["without_document"] == "/v3/questionnaire"


def test_legacy_v3_entry_keeps_narrative_compatibility():
    response = client.post(
        "/api/v3/sessions",
        headers=_guest_headers(idempotency_key="legacy-entry-narrative-1"),
        json={},
    )

    assert response.status_code == 201
    choices = {choice["id"]: choice["next_route"] for choice in _v3_data(response)["choices"]}
    assert choices["without_document"] == "/v3/narrative"

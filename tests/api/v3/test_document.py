"""V3 document ownership and API (Issue #99 step 1)."""

import base64
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _v3_data(response):
    payload = response.json()
    if "data" not in payload:
        raise AssertionError(
            f"unexpected {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload["data"]


def _guest_headers() -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _new_flow_session(headers) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"seed-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _create_document(headers, session_id, *, storage_path=None):
    return client.post(
        "/api/v3/documents",
        headers=headers,
        json={
            "session_id": session_id,
            "original_filename": "sample.png",
            "file_type": "png",
            "file_size_bytes": 1024,
        },
    )


def test_create_list_delete_document_is_ownership_scoped():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    created = _create_document(headers, session_id)
    assert created.status_code == 201, created.text
    document_id = _v3_data(created)["document_id"]

    listed = client.get(f"/api/v3/sessions/{session_id}/documents", headers=headers)
    assert listed.status_code == 200
    assert _v3_data(listed)["total"] == 1
    assert _v3_data(listed)["documents"][0]["document_id"] == document_id

    deleted = client.delete(f"/api/v3/documents/{document_id}", headers=headers)
    assert deleted.status_code == 200

    after = client.get(f"/api/v3/sessions/{session_id}/documents", headers=headers)
    assert _v3_data(after)["total"] == 0


def test_cross_user_document_isolation():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    document_id = _v3_data(_create_document(headers, session_id))["document_id"]

    stranger = _guest_headers()
    denied_list = client.get(f"/api/v3/sessions/{session_id}/documents", headers=stranger)
    assert denied_list.status_code == 404
    denied_delete = client.delete(f"/api/v3/documents/{document_id}", headers=stranger)
    assert denied_delete.status_code == 404


def test_create_document_requires_owned_session():
    headers = _guest_headers()
    other_headers = _guest_headers()
    other_session = _new_flow_session(other_headers)

    response = _create_document(headers, other_session)
    assert response.status_code == 404

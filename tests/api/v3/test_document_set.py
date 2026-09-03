"""V3.1 document-set (1-3) tests (Issue #99 step 2)."""

import base64
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.v3.document import DocumentSet


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


def _transition(headers, session_id, key, body):
    return client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )


def _create_document(headers, session_id, filename="sample.png"):
    response = client.post(
        "/api/v3/documents",
        headers=headers,
        json={
            "session_id": session_id,
            "original_filename": filename,
            "file_type": "png",
            "file_size_bytes": 1024,
            "storage_path": f"docs/{uuid.uuid4().hex}",
            "status": "uploaded",
            "ocr_text": "材料内容",
        },
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["document_id"]


def _replace_set(headers, session_id, key, doc_ids, expected_input_revision):
    return client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": key},
        json={
            "session_id": session_id,
            "expected_input_revision": expected_input_revision,
            "document_ids": doc_ids,
        },
    )


def test_replace_document_set_orders_and_revisions():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id, "a.png")
    doc_b = _create_document(headers, session_id, "b.png")
    doc_c = _create_document(headers, session_id, "c.png")

    first = _replace_set(headers, session_id, "set-1", [doc_a, doc_b], 2)
    assert first.status_code == 201, first.text
    data = _v3_data(first)
    assert data["revision"] == 1
    assert [d["document_id"] for d in data["documents"]] == [doc_a, doc_b]
    assert data["input_revision"] == 3

    # Replace with a 3-doc set -> revision 2.
    second = _replace_set(headers, session_id, "set-2", [doc_c, doc_a, doc_b], 3)
    assert second.status_code == 201, second.text
    data = _v3_data(second)
    assert data["revision"] == 2
    assert [d["document_id"] for d in data["documents"]] == [doc_c, doc_a, doc_b]

    active = _v3_data(
        client.get(f"/api/v3/sessions/{session_id}/document-sets/active", headers=headers)
    )
    assert active["revision"] == 2


def test_document_set_rejects_invalid_size_duplicate_and_cross_user():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)

    # Empty set (rejected by schema min_length=1).
    empty = _replace_set(headers, session_id, "set-empty", [], 2)
    assert empty.status_code == 422

    # Duplicate (rejected by schema uniqueness validator).
    dup = _replace_set(headers, session_id, "set-dup", [doc_a, doc_a], 2)
    assert dup.status_code == 422

    # Cross-user document (rejected by service ownership).
    stranger = _guest_headers()
    stranger_session = _new_flow_session(stranger)
    stranger_doc = _create_document(stranger, stranger_session)
    denied = _replace_set(headers, session_id, "set-cross", [stranger_doc], 2)
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_document_set_requires_matching_input_revision():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    response = _replace_set(headers, session_id, "set-1", [doc_a], 99)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"

"""V3.1 document relevance tests (Issue #99 step 3)."""

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


def _transition(headers, session_id, key, body):
    return client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )


def _create_document(headers, session_id):
    response = client.post(
        "/api/v3/documents",
        headers=headers,
        json={
            "session_id": session_id,
            "original_filename": "sample.png",
            "file_type": "png",
            "file_size_bytes": 1024,
            "storage_path": f"docs/{uuid.uuid4().hex}",
            "status": "uploaded",
            "ocr_text": "材料内容",
        },
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["document_id"]


def _make_set(headers, session_id, doc_ids, expected_input_revision):
    response = client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": f"set-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": expected_input_revision,
            "document_ids": doc_ids,
        },
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)


def test_record_and_read_relevance():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    doc_b = _create_document(headers, session_id)
    set_data = _make_set(headers, session_id, [doc_a, doc_b], 2)
    set_id = set_data["document_set_id"]

    recorded = client.post(
        f"/api/v3/document-sets/{set_id}/relevance",
        headers=headers,
        json={
            "document_set_id": set_id,
            "document_set_revision": 1,
            "evaluator": "understanding_rule",
            "evaluator_version": "v1",
            "items": [
                {"document_id": doc_a, "outcome": "VALID", "reason_codes": []},
                {"document_id": doc_b, "outcome": "IRRELEVANT", "reason_codes": ["UNRELATED_TOPIC"]},
            ],
        },
    )
    assert recorded.status_code == 201, recorded.text
    data = _v3_data(recorded)
    assert len(data["items"]) == 2
    outcomes = {item["document_id"]: item["outcome"] for item in data["items"]}
    assert outcomes[doc_a] == "VALID"
    assert outcomes[doc_b] == "IRRELEVANT"

    read = _v3_data(
        client.get(f"/api/v3/document-sets/{set_id}/relevance", headers=headers)
    )
    assert {item["document_id"]: item["outcome"] for item in read["items"]} == outcomes


def test_relevance_rejects_document_not_in_set():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    set_id = _make_set(headers, session_id, [doc_a], 2)["document_set_id"]

    outsider = _create_document(headers, session_id)
    response = client.post(
        f"/api/v3/document-sets/{set_id}/relevance",
        headers=headers,
        json={
            "document_set_id": set_id,
            "document_set_revision": 1,
            "items": [{"document_id": outsider, "outcome": "VALID", "reason_codes": []}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RELEVANCE_DOCUMENT_NOT_IN_SET"


def test_relevance_is_cross_user_isolated():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    set_id = _make_set(headers, session_id, [doc_a], 2)["document_set_id"]

    stranger = _guest_headers()
    denied = client.get(
        f"/api/v3/document-sets/{set_id}/relevance", headers=stranger
    )
    assert denied.status_code == 404

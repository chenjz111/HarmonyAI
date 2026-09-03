"""V3.1 document relevance tests (Issue #99 step 3).

Write is internal (record_relevance service); the frontend reads outcome only.
"""

import base64
from contextlib import contextmanager
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models.v3.identity import UserIdentity
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentRelevanceRecordRequest
from backend.app.services.v3.document_relevance_service import (
    InvalidRelevance,
    record_relevance,
)


client = TestClient(app)


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _v3_data(response):
    payload = response.json()
    if "data" not in payload:
        raise AssertionError(
            f"unexpected {response.status_code}: {json.dumps(payload, ensure_ascii=False)}"
        )
    return payload["data"]


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _guest_headers() -> dict[str, str]:
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _principal(headers) -> AuthPrincipal:
    public_user_id = _public_user_id(headers["Authorization"].split()[1])
    with _seed_db() as session:
        user = (
            session.query(UserIdentity)
            .filter(UserIdentity.public_user_id == public_user_id)
            .one()
        )
        return AuthPrincipal(
            internal_user_pk=user.internal_user_pk,
            public_user_id=public_user_id,
            auth_type="guest",
            guest_expires_at="2030-01-01T00:00:00Z",
        )


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
    set_id = _make_set(headers, session_id, [doc_a, doc_b], 2)["document_set_id"]

    principal = _principal(headers)
    request = DocumentRelevanceRecordRequest(
        document_set_id=set_id,
        document_set_revision=1,
        evaluator="understanding_rule",
        evaluator_version="v1",
        items=[
            {"document_id": doc_a, "outcome": "VALID", "reason_codes": []},
            {"document_id": doc_b, "outcome": "IRRELEVANT", "reason_codes": ["UNRELATED_TOPIC"]},
        ],
    )
    with _seed_db() as session:
        data = record_relevance(session, principal, request)
    outcomes = {item.document_id: item.outcome for item in data.items}
    assert outcomes[doc_a] == "VALID"
    assert outcomes[doc_b] == "IRRELEVANT"

    read = _v3_data(
        client.get(f"/api/v3/document-sets/{set_id}/relevance", headers=headers)
    )
    assert {item["document_id"]: item["outcome"] for item in read["items"]} == outcomes


def test_relevance_rejects_partial_coverage():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    doc_b = _create_document(headers, session_id)
    set_id = _make_set(headers, session_id, [doc_a, doc_b], 2)["document_set_id"]

    principal = _principal(headers)
    request = DocumentRelevanceRecordRequest(
        document_set_id=set_id,
        document_set_revision=1,
        items=[{"document_id": doc_a, "outcome": "VALID", "reason_codes": []}],
    )
    with _seed_db() as session:
        try:
            record_relevance(session, principal, request)
            raise AssertionError("expected InvalidRelevance")
        except InvalidRelevance as exc:
            assert exc.code == "RELEVANCE_COVERAGE_INCOMPLETE"


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

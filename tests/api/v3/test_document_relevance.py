"""V3.1 document relevance tests (Issue #110 closeout).

Write is internal (record_relevance service); the frontend reads the frozen
per-set DocumentRelevanceResult only.
"""

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.document import DocumentRelevance, DocumentSet
from backend.app.models.v3.identity import UserIdentity
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentRelevanceRecordRequest
from backend.app.schemas.v3.flow_v31 import DocumentRelevanceResult, DocumentSetRef
from backend.app.services.v3.document_relevance_evaluator import (
    DocumentRelevanceEvaluationError,
    ensure_document_set_relevance,
)
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
    set_id = _make_set(headers, session_id, [doc_a], 2)["document_set_id"]

    principal = _principal(headers)
    request = DocumentRelevanceRecordRequest(
        document_set_id=set_id,
        document_set_revision=1,
        run_id="run_1",
        revision=1,
        outcome="VALID",
        reason_code="VALID_RECENT_CLINICAL_DOCUMENT",
        reason="资料可用于本次状态理解。",
        evaluator="understanding_rule",
        evaluator_version="v1",
    )
    with _seed_db() as session:
        data = record_relevance(session, principal, request)
    assert data.outcome.value == "VALID"
    assert data.may_enter_summary is True
    assert data.may_form_evidence is True
    assert data.may_enter_agent2 is True

    read = _v3_data(
        client.get(f"/api/v3/document-sets/{set_id}/relevance", headers=headers)
    )
    assert read["outcome"] == "VALID"
    assert read["reason_code"] == "VALID_RECENT_CLINICAL_DOCUMENT"


def test_relevance_non_valid_gates_are_false():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    set_id = _make_set(headers, session_id, [doc_a], 2)["document_set_id"]

    principal = _principal(headers)
    request = DocumentRelevanceRecordRequest(
        document_set_id=set_id,
        document_set_revision=1,
        run_id="run_1",
        revision=1,
        outcome="IRRELEVANT",
        reason_code="UNRELATED_TOPIC",
        reason="与本次健康状态评估无关。",
    )
    with _seed_db() as session:
        data = record_relevance(session, principal, request)
    assert data.may_enter_summary is False
    assert data.may_form_evidence is False
    assert data.may_enter_agent2 is False


def test_relevance_rejects_revision_mismatch():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    doc_a = _create_document(headers, session_id)
    set_id = _make_set(headers, session_id, [doc_a], 2)["document_set_id"]

    principal = _principal(headers)
    request = DocumentRelevanceRecordRequest(
        document_set_id=set_id,
        document_set_revision=99,
        run_id="run_1",
        revision=1,
        outcome="VALID",
        reason_code="VALID_RECENT_CLINICAL_DOCUMENT",
        reason="资料可用于本次状态理解。",
    )
    with _seed_db() as session:
        try:
            record_relevance(session, principal, request)
            raise AssertionError("expected InvalidRelevance")
        except InvalidRelevance as exc:
            assert exc.code == "RELEVANCE_REVISION_MISMATCH"


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


class _FakeRelevanceEvaluator:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = 0

    def evaluate(
        self,
        *,
        document_set_id,
        set_revision,
        input_revision,
        ordered_ocr_texts,
    ):
        self.calls += 1
        if self.fail:
            raise DocumentRelevanceEvaluationError(
                "RELEVANCE_PROVIDER_UNAVAILABLE",
                "资料可用性判断服务暂不可用。",
            )
        assert input_revision >= 1
        assert ordered_ocr_texts == ["近期门诊记录：睡眠欠佳。"]
        return DocumentRelevanceResult(
            schema_version="document_relevance_result_v3.1",
            relevance_result_id=f"provider_{uuid.uuid4().hex}",
            run_id=f"run_{uuid.uuid4().hex}",
            revision=1,
            document_set_ref=DocumentSetRef(
                document_set_id=document_set_id,
                revision=set_revision,
            ),
            outcome="VALID",
            reason_code="VALID_RECENT_CLINICAL_DOCUMENT",
            reason="资料可用于本次状态理解。",
            may_enter_summary=True,
            may_form_evidence=True,
            may_enter_agent2=True,
            completed_at=datetime.now(timezone.utc),
        )


@contextmanager
def _current_set_rows(headers, session_id, set_id, document_id):
    principal = _principal(headers)
    with _seed_db() as db:
        db.query(Document).filter(Document.document_id == document_id).one().ocr_text = (
            "近期门诊记录：睡眠欠佳。"
        )
        db.commit()
        session_row = db.query(SessionModel).filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == principal.internal_user_pk,
        ).one()
        set_row = db.query(DocumentSet).filter(
            DocumentSet.document_set_id == set_id
        ).one()
        yield db, session_row, set_row


def test_missing_relevance_invokes_evaluator_once():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers,
        session_id,
        "select-evaluator",
        {
            "expected_input_revision": 1,
            "action": "select_mode",
            "input_mode": "with_document",
        },
    )
    document_id = _create_document(headers, session_id)
    set_data = _make_set(headers, session_id, [document_id], 2)
    evaluator = _FakeRelevanceEvaluator()

    with _current_set_rows(
        headers, session_id, set_data["document_set_id"], document_id
    ) as (db, session_row, set_row):
        first = ensure_document_set_relevance(db, session_row, set_row, evaluator)
        second = ensure_document_set_relevance(db, session_row, set_row, evaluator)

    assert first.relevance_result_id == second.relevance_result_id
    assert evaluator.calls == 1


def test_real_provider_failure_never_records_valid():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers,
        session_id,
        "select-failing-evaluator",
        {
            "expected_input_revision": 1,
            "action": "select_mode",
            "input_mode": "with_document",
        },
    )
    document_id = _create_document(headers, session_id)
    set_data = _make_set(headers, session_id, [document_id], 2)
    evaluator = _FakeRelevanceEvaluator(fail=True)

    with _current_set_rows(
        headers, session_id, set_data["document_set_id"], document_id
    ) as (db, session_row, set_row):
        with pytest.raises(DocumentRelevanceEvaluationError):
            ensure_document_set_relevance(db, session_row, set_row, evaluator)
        assert (
            db.query(DocumentRelevance)
            .filter(
                DocumentRelevance.document_set_id == set_data["document_set_id"]
            )
            .count()
            == 0
        )

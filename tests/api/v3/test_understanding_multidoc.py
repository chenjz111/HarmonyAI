"""V3.1 Understanding consumption of the authoritative DocumentSet."""

import base64
from contextlib import contextmanager
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.document import DocumentRelevance
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.understanding import UnderstandingRun
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentRelevanceRecordRequest
from backend.app.services.v3.document_relevance_service import record_relevance
from backend.app.services.v3.activity_service import (
    AssessmentInputNotReady,
    validate_assessment_input_readiness,
)
from backend.app.services.v3 import understanding_service


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
        raise AssertionError(f"unexpected {response.status_code}: {payload}")
    return payload["data"]


def _guest_headers():
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _public_user_id(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _principal(headers: dict[str, str]) -> AuthPrincipal:
    public_user_id = _public_user_id(headers["Authorization"].split()[1])
    with _seed_db() as db:
        identity = (
            db.query(UserIdentity)
            .filter(UserIdentity.public_user_id == public_user_id)
            .one()
        )
    return AuthPrincipal(
        internal_user_pk=identity.internal_user_pk,
        public_user_id=public_user_id,
        auth_type="guest",
        guest_expires_at="2030-01-01T00:00:00Z",
    )


def _new_owner_session(headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"session-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _transition(headers, session_id, body):
    response = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"transition-{uuid.uuid4().hex}"},
        json=body,
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)


def _seed_document(db, *, user_pk: int, session_id: str, text: str) -> str:
    document_id = f"doc_{uuid.uuid4().hex}"
    db.add(
        Document(
            user_id=user_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename=f"{document_id}.txt",
            file_type="png",
            file_size_bytes=1024,
            storage_path=f"docs/{document_id}",
            status="uploaded",
            ocr_text=text,
            ocr_confidence="high",
            ocr_error_code=None,
        )
    )
    db.commit()
    return document_id


def _document_source(document_id: str) -> dict[str, str]:
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "document",
        "processing_status": "ready",
        "text_ref": document_id,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _make_document_set(headers, session_id, document_ids):
    _transition(
        headers,
        session_id,
        {
            "expected_input_revision": 1,
            "action": "select_mode",
            "input_mode": "with_document",
        },
    )
    result = client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": f"set-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": 2,
            "document_ids": document_ids,
        },
    )
    assert result.status_code == 201, result.text
    return _v3_data(result)


def _record_relevance(headers, document_set_id, revision, document_ids, outcomes):
    request = DocumentRelevanceRecordRequest(
        document_set_id=document_set_id,
        document_set_revision=revision,
        items=[
            {"document_id": document_id, "outcome": outcome, "reason_codes": []}
            for document_id, outcome in zip(document_ids, outcomes, strict=True)
        ],
        evaluator="test",
        evaluator_version="v1",
    )
    with _seed_db() as db:
        record_relevance(db, _principal(headers), request)


def _post_understanding(headers, session_id, document_ids, input_revision):
    return client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": f"understanding-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "session_id": session_id,
            "expected_input_revision": input_revision,
            "inputs": [_document_source(document_id) for document_id in document_ids],
        },
    )


def _seed_owner_documents(headers, session_id, count):
    with _seed_db() as db:
        user_id = _public_user_id(headers["Authorization"].split()[1])
        user_pk = (
            db.query(UserIdentity)
            .filter(UserIdentity.public_user_id == user_id)
            .one()
            .internal_user_pk
        )
        return [
            _seed_document(db, user_pk=user_pk, session_id=session_id, text=f"资料 {index}")
            for index in range(1, count + 1)
        ]


def test_v31_understanding_consumes_one_valid_document_from_active_set():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID"],
    )

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["case_summary"]["source_document_ids"] == document_ids
    assert data["source_statuses"][0]["relevance_outcome"] == "VALID"


def test_v31_understanding_processes_three_valid_documents_in_saved_order():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 3)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID", "VALID", "VALID"],
    )

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["case_summary"]["source_document_ids"] == document_ids
    assert [item["relevance_outcome"] for item in data["source_statuses"]] == [
        "VALID",
        "VALID",
        "VALID",
    ]


def test_v31_understanding_excludes_invalid_document_from_mixed_set():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 2)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID", "IRRELEVANT"],
    )

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["case_summary"]["source_document_ids"] == [document_ids[0]]
    assert [item["relevance_outcome"] for item in data["source_statuses"]] == [
        "VALID",
        "IRRELEVANT",
    ]
    assert data["source_statuses"][1]["status"] == "skipped"


def test_v31_understanding_does_not_enter_summary_when_all_documents_invalid():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["INVALID"],
    )

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["status"] == "failed"
    assert data["case_summary"] is None
    assert data["source_statuses"][0]["relevance_outcome"] == "INVALID"


def test_v31_understanding_requires_relevance_before_summary():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    _make_document_set(headers, session_id, document_ids)

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "RELEVANCE_NOT_READY"


def test_v31_understanding_does_not_auto_discard_insufficient_relevance():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["INSUFFICIENT"],
    )

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "RELEVANCE_INSUFFICIENT"


def test_v31_understanding_rejects_active_set_from_another_user():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)

    stranger = _guest_headers()
    stranger_session = _new_owner_session(stranger)
    stranger_docs = _seed_owner_documents(stranger, stranger_session, 1)
    stranger_set = _make_document_set(stranger, stranger_session, stranger_docs)

    with _seed_db() as db:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        session.input_mode = "with_document"
        session.active_document_set_id = stranger_set["document_set_id"]
        session.active_document_id = stranger_docs[0]
        session.input_revision = 3
        db.commit()

    response = _post_understanding(headers, session_id, stranger_docs, 3)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DOCUMENT_SET_NOT_ACTIVE"


def test_v31_understanding_rejects_active_set_from_another_session():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    other_session_id = _new_owner_session(headers)
    other_docs = _seed_owner_documents(headers, other_session_id, 1)
    other_set = _make_document_set(headers, other_session_id, other_docs)

    with _seed_db() as db:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        session.input_mode = "with_document"
        session.active_document_set_id = other_set["document_set_id"]
        session.active_document_id = other_docs[0]
        session.input_revision = 3
        db.commit()

    response = _post_understanding(headers, session_id, other_docs, 3)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DOCUMENT_SET_NOT_ACTIVE"


def test_v31_understanding_rejects_superseded_document_set_even_if_pointer_is_stale():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    first_docs = _seed_owner_documents(headers, session_id, 1)
    first_set = _make_document_set(headers, session_id, first_docs)
    _record_relevance(
        headers,
        first_set["document_set_id"],
        first_set["revision"],
        first_docs,
        ["VALID"],
    )

    second_docs = _seed_owner_documents(headers, session_id, 1)
    second_set = client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": f"set-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": 3,
            "document_ids": second_docs,
        },
    )
    assert second_set.status_code == 201, second_set.text

    with _seed_db() as db:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        session.active_document_set_id = first_set["document_set_id"]
        session.active_document_id = first_docs[0]
        session.input_revision = 4
        db.commit()

    response = _post_understanding(headers, session_id, first_docs, 4)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DOCUMENT_SET_NOT_ACTIVE"


def test_v31_document_facts_keep_concrete_document_source(monkeypatch):
    from backend.ai_engine.v3.understanding_provider import (
        MockUnderstandingProvider,
        UnderstandingProviderChain,
    )
    from backend.app.schemas.v3.understanding import (
        TextSpan,
        UnderstandingProviderFact,
        UnderstandingProviderResponse,
    )

    provider = MockUnderstandingProvider(
        UnderstandingProviderResponse(
            status="success",
            facts=[
                UnderstandingProviderFact(
                    claim_code="sleep_unrefreshing",
                    display_name="睡眠后仍感疲惫",
                    category="sleep",
                    value={"type": "severity", "value": "moderate"},
                    time_window="past_7_days",
                    negated=False,
                    subject="self",
                    span=TextSpan(start=0, end=2),
                    extraction_confidence=0.8,
                )
            ],
            warnings=[],
        )
    )
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: UnderstandingProviderChain(cloud=None, local=None, rule=provider),
    )

    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID"],
    )

    response = _post_understanding(headers, session_id, document_ids, 3)

    assert response.status_code == 201, response.text
    fact = _v3_data(response)["normalized_facts"][0]
    assert fact["source_refs"][0]["source_id"] == document_ids[0]
    assert fact["source_refs"][0]["source_type"] == "document"


def test_v31_confirmation_binds_the_same_document_set_snapshot():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID"],
    )
    understanding = _post_understanding(headers, session_id, document_ids, 3)
    understanding_id = _v3_data(understanding)["understanding_id"]

    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"confirm-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 3,
            "decision": "confirm",
        },
    )

    assert response.status_code == 201, response.text
    result = _v3_data(response)
    assert (
        result["understanding"]["source_statuses"][0]["relevance_outcome"]
        == "VALID"
    )
    with _seed_db() as db:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        assert session.active_understanding_id == understanding_id
        assert session.active_understanding_revision == 2


def test_assessment_readiness_rejects_a_stale_document_set_snapshot():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    first_docs = _seed_owner_documents(headers, session_id, 1)
    first_set = _make_document_set(headers, session_id, first_docs)
    _record_relevance(
        headers,
        first_set["document_set_id"],
        first_set["revision"],
        first_docs,
        ["VALID"],
    )
    understanding_id = _v3_data(
        _post_understanding(headers, session_id, first_docs, 3)
    )["understanding_id"]
    confirmed = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"confirm-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 3,
            "decision": "confirm",
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    second_docs = _seed_owner_documents(headers, session_id, 1)
    replacement = client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": f"set-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": 4,
            "document_ids": second_docs,
        },
    )
    assert replacement.status_code == 201, replacement.text

    with _seed_db() as db:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        session.active_document_set_id = first_set["document_set_id"]
        session.active_document_id = first_docs[0]
        session.active_understanding_id = understanding_id
        session.active_understanding_revision = 2
        session.input_revision = 5
        run = db.query(UnderstandingRun).filter(
            UnderstandingRun.understanding_id == understanding_id
        ).one()
        try:
            validate_assessment_input_readiness(db, session)
        except AssessmentInputNotReady as error:
            assert error.code == "DOCUMENT_SET_NOT_ACTIVE"
        else:
            raise AssertionError("stale document set must not pass readiness")


def test_assessment_readiness_rejects_re_evaluated_relevance_for_old_understanding():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID"],
    )
    understanding_id = _v3_data(
        _post_understanding(headers, session_id, document_ids, 3)
    )["understanding_id"]
    confirmed = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"confirm-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 3,
            "decision": "confirm",
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    with _seed_db() as db:
        relevance = db.query(DocumentRelevance).filter(
            DocumentRelevance.document_set_id == document_set["document_set_id"],
            DocumentRelevance.document_id == document_ids[0],
        ).one()
        relevance.outcome = "IRRELEVANT"
        relevance.reason_codes_json = ["UNRELATED_TOPIC"]
        db.commit()

    with _seed_db() as db:
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        try:
            validate_assessment_input_readiness(db, session)
        except AssessmentInputNotReady as error:
            assert error.code == "DOCUMENT_SET_NOT_ACTIVE"
        else:
            raise AssertionError("updated relevance must invalidate old understanding")


def test_v31_discarded_document_set_cannot_be_used_for_understanding():
    headers = _guest_headers()
    session_id = _new_owner_session(headers)
    document_ids = _seed_owner_documents(headers, session_id, 1)
    document_set = _make_document_set(headers, session_id, document_ids)
    _record_relevance(
        headers,
        document_set["document_set_id"],
        document_set["revision"],
        document_ids,
        ["VALID"],
    )

    discarded = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"discard-{uuid.uuid4().hex}"},
        json={
            "expected_input_revision": 3,
            "action": "discard_document",
        },
    )
    assert discarded.status_code == 201, discarded.text

    response = _post_understanding(headers, session_id, document_ids, 4)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "INPUT_SOURCE_MISMATCH"

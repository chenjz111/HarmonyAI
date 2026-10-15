"""DocumentSet relevance must gate the V3.1 Understanding boundary."""

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
from backend.app.models.v3.document import DocumentSet
from backend.app.models.v3.identity import UserIdentity
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentRelevanceRecordRequest
from backend.app.schemas.v3.flow_v31 import DocumentRelevanceResult, DocumentSetRef
from backend.app.services.v3 import document_relevance_evaluator
from backend.app.services.v3.document_relevance_service import record_relevance


client = TestClient(app)


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _data(response):
    return response.json()["data"]


def _guest_headers():
    token = _data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _principal(headers):
    token = headers["Authorization"].split()[1]
    encoded = token.split(".")[1]
    encoded += "=" * (-len(encoded) % 4)
    public_user_id = json.loads(base64.urlsafe_b64decode(encoded))["sub"]
    with _seed_db() as db:
        user = db.query(UserIdentity).filter(
            UserIdentity.public_user_id == public_user_id
        ).one()
        return AuthPrincipal(
            internal_user_pk=user.internal_user_pk,
            public_user_id=public_user_id,
            auth_type="guest",
            guest_expires_at="2030-01-01T00:00:00Z",
        )


def _owner_session(headers):
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"session-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    session_id = _data(response)["session_id"]
    selected = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"mode-{uuid.uuid4().hex}"},
        json={
            "expected_input_revision": 1,
            "action": "select_mode",
            "input_mode": "with_document",
        },
    )
    assert selected.status_code == 201, selected.text
    return session_id


def _documents(headers, session_id, count):
    principal = _principal(headers)
    ids = []
    with _seed_db() as db:
        session_row = db.query(SessionModel).filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == principal.internal_user_pk,
        ).one()
        for index in range(count):
            document_id = f"doc_{uuid.uuid4().hex}"
            db.add(
                Document(
                    user_id=principal.internal_user_pk,
                    session_id=session_row.session_id,
                    document_id=document_id,
                    original_filename=f"case-{index + 1}.png",
                    file_type="png",
                    file_size_bytes=1024,
                    storage_path=f"documents/{document_id}",
                    status="uploaded",
                    ocr_text=f"第{index + 1}份资料：近期睡眠不稳。",
                    ocr_confidence="high",
                )
            )
            ids.append(document_id)
        db.commit()
    return ids


def _document_set(headers, session_id, document_ids):
    response = client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": f"set-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": 2,
            "document_ids": document_ids,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


def _record(headers, document_set, outcome):
    with _seed_db() as db:
        record_relevance(
            db,
            _principal(headers),
            DocumentRelevanceRecordRequest(
                document_set_id=document_set["document_set_id"],
                document_set_revision=document_set["revision"],
                run_id=f"relrun_{uuid.uuid4().hex}",
                revision=1,
                outcome=outcome,
                reason_code=f"TEST_{outcome}",
                reason="测试资料可用性门禁。",
                evaluator="test",
                evaluator_version="v1",
            ),
        )


def _understand(headers, session_id, document_ids):
    return client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": f"und-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "session_id": session_id,
            "expected_input_revision": 3,
            "inputs": [
                {
                    "source_id": f"source-{index + 1}",
                    "source_type": "document",
                    "processing_status": "ready",
                    "text_ref": document_id,
                    "captured_at": "2026-09-08T00:00:00Z",
                }
                for index, document_id in enumerate(document_ids)
            ],
        },
    )


def test_valid_document_set_enters_understanding_in_saved_order():
    headers = _guest_headers()
    session_id = _owner_session(headers)
    document_ids = _documents(headers, session_id, 3)
    document_set = _document_set(headers, session_id, document_ids)
    _record(headers, document_set, "VALID")

    response = _understand(headers, session_id, document_ids)

    assert response.status_code == 201, response.text
    result = _data(response)
    assert [item["source_id"] for item in result["source_statuses"]] == [
        "source-1",
        "source-2",
        "source-3",
    ]
    assert all(item["status"] == "ready" for item in result["source_statuses"])


@pytest.mark.parametrize("outcome", ["INVALID", "IRRELEVANT"])
def test_non_valid_document_set_cannot_enter_understanding(outcome):
    headers = _guest_headers()
    session_id = _owner_session(headers)
    document_ids = _documents(headers, session_id, 1)
    document_set = _document_set(headers, session_id, document_ids)
    _record(headers, document_set, outcome)

    response = _understand(headers, session_id, document_ids)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DOCUMENT_RELEVANCE_BLOCKED"


def test_insufficient_document_set_remains_pending():
    headers = _guest_headers()
    session_id = _owner_session(headers)
    document_ids = _documents(headers, session_id, 1)
    document_set = _document_set(headers, session_id, document_ids)
    _record(headers, document_set, "INSUFFICIENT")

    response = _understand(headers, session_id, document_ids)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DOCUMENT_RELEVANCE_INSUFFICIENT"


def test_understanding_waits_for_document_set_relevance():
    headers = _guest_headers()
    session_id = _owner_session(headers)
    document_ids = _documents(headers, session_id, 1)
    _document_set(headers, session_id, document_ids)

    response = _understand(headers, session_id, document_ids)

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "DOCUMENT_RELEVANCE_NOT_READY"


def test_understanding_executes_missing_relevance_through_configured_evaluator(
    monkeypatch,
):
    headers = _guest_headers()
    session_id = _owner_session(headers)
    document_ids = _documents(headers, session_id, 2)
    document_set = _document_set(headers, session_id, document_ids)

    class RuntimeEvaluator:
        model = "qwen-test"

        def __init__(self):
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
            assert input_revision == 3
            assert ordered_ocr_texts == [
                "第1份资料：近期睡眠不稳。",
                "第2份资料：近期睡眠不稳。",
            ]
            return DocumentRelevanceResult(
                schema_version="document_relevance_result_v3.1",
                relevance_result_id="provider_result",
                run_id="runtime_relevance_run",
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

    evaluator = RuntimeEvaluator()
    monkeypatch.setattr(
        document_relevance_evaluator,
        "relevance_evaluator_from_environment",
        lambda: evaluator,
    )

    response = _understand(headers, session_id, document_ids)

    assert response.status_code == 201, response.text
    assert evaluator.calls == 1
    relevance = _data(
        client.get(
            f"/api/v3/document-sets/{document_set['document_set_id']}/relevance",
            headers=headers,
        )
    )
    assert relevance["outcome"] == "VALID"


def test_replace_document_invalidates_old_set_and_old_understanding():
    headers = _guest_headers()
    session_id = _owner_session(headers)
    old_document_ids = _documents(headers, session_id, 1)
    old_set = _document_set(headers, session_id, old_document_ids)
    _record(headers, old_set, "VALID")
    created = _understand(headers, session_id, old_document_ids)
    assert created.status_code == 201, created.text
    understanding_id = _data(created)["understanding_id"]

    replacement_document_id = _documents(headers, session_id, 1)[0]
    replaced = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"replace-{uuid.uuid4().hex}"},
        json={
            "expected_input_revision": 3,
            "action": "replace_document",
            "document_id": replacement_document_id,
        },
    )
    assert replaced.status_code == 201, replaced.text
    replaced_state = _data(replaced)
    principal = _principal(headers)
    with _seed_db() as db:
        session_row = db.query(SessionModel).filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == principal.internal_user_pk,
        ).one()
        assert session_row.active_document_set_id is None
        persisted_old_set = db.query(DocumentSet).filter(
            DocumentSet.document_set_id == old_set["document_set_id"]
        ).one()
        assert persisted_old_set.status == "superseded"

    confirmed = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"confirm-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": replaced_state["input_revision"],
            "decision": "confirm",
            "changes": [],
            "reprocess_requested": False,
        },
    )
    assert confirmed.status_code == 409, confirmed.text

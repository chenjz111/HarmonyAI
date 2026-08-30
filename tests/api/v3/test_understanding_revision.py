"""Owner Flow Amendment 001 §3.2/§3.3/§4.2 — Understanding v3.1 run + revision."""

import uuid

from fastapi.testclient import TestClient
import pytest

from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    UnderstandingProviderChain,
)
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.user import User
from backend.app.models.v3.identity import UserIdentity
from backend.app.routers.v3 import understanding_router
from backend.app.schemas.v3.understanding import (
    TextSpan,
    UnderstandingProviderFact,
    UnderstandingProviderResponse,
)


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def _guest_token() -> str:
    return _v3_data(client.post("/api/v3/auth/guest"))["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_flow_session(token: str) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={
            **_headers(token),
            "Idempotency-Key": f"mk-sess-{uuid.uuid4().hex}",
        },
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _create_ocr_document(
    db_factory,
    token: str,
    session_id: str,
    *,
    document_id: str,
    ocr_text: str = "近期入睡困难，白天精神不足。",
    status: str = "uploaded",
    ocr_confidence: str = "high",
    ocr_error_code: str | None = None,
    ocr_result_json: object | None = None,
) -> None:
    db = db_factory()
    user = db.query(User).order_by(User.id.desc()).first()
    identity = db.query(UserIdentity).filter(
        UserIdentity.internal_user_pk == user.id
    ).first()
    internal_pk = identity.internal_user_pk if identity is not None else user.id
    db.add(
        Document(
            user_id=internal_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename="material.jpg",
            file_type="jpg",
            file_size_bytes=1024,
            storage_path="uploads/material.jpg",
            status=status,
            ocr_text=ocr_text,
            ocr_confidence=ocr_confidence,
            ocr_error_code=ocr_error_code,
            ocr_result_json=(
                {"page_results": [], "average_confidence": 0.9}
                if ocr_result_json is None
                else ocr_result_json
            ),
            ocr_confirmed=True,
        )
    )
    db.commit()
    db.close()


def _replace_document(token: str, session_id: str, document_id: str) -> int:
    response = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={
            **_headers(token),
            "Idempotency-Key": f"mk-replace-{uuid.uuid4().hex}",
        },
        json={
            "action": "replace_document",
            "expected_input_revision": 1,
            "document_id": document_id,
        },
    )
    assert response.status_code == 200, response.text
    return _v3_data(response)["input_revision"]


def _prepare_with_document(
    token: str,
    db_factory,
    *,
    ocr_text: str = "近期入睡困难，白天精神不足。",
    status: str = "uploaded",
    ocr_confidence: str = "high",
    ocr_error_code: str | None = None,
    ocr_result_json: object | None = None,
) -> tuple[str, str]:
    session_id = _create_flow_session(token)
    document_id = f"doc_{uuid.uuid4().hex}"
    _create_ocr_document(
        db_factory,
        token,
        session_id,
        document_id=document_id,
        ocr_text=ocr_text,
        status=status,
        ocr_confidence=ocr_confidence,
        ocr_error_code=ocr_error_code,
        ocr_result_json=ocr_result_json,
    )
    _replace_document(token, session_id, document_id)
    return session_id, document_id


def _understanding_run_body(
    session_id: str,
    document_id: str,
    expected_input_revision: int,
    *,
    processing_status: str = "ready",
    source_id: str | None = None,
) -> dict:
    return {
        "schema_version": "understanding_v3.1",
        "session_id": session_id,
        "expected_input_revision": expected_input_revision,
        "inputs": [
            {
                "source_id": source_id or document_id,
                "source_type": "document",
                "processing_status": processing_status,
                "text": "客户端文本会被服务端 OCR 权威文本覆盖",
                "captured_at": "2026-08-01T00:00:00Z",
            }
        ],
    }


def _mock_chain(*, facts: list | None = None) -> UnderstandingProviderChain:
    if facts is None:
        facts = [
            UnderstandingProviderFact(
                claim_code="sleep_unrefreshing",
                display_name="睡眠后仍感疲惫",
                category="sleep",
                value={"type": "severity", "value": "moderate"},
                time_window="past_7_days",
                negated=False,
                subject="self",
                span=TextSpan(start=0, end=6),
                extraction_confidence=0.8,
            )
        ]
    provider = MockUnderstandingProvider(
        UnderstandingProviderResponse(
            status="success",
            facts=facts,
            warnings=[],
        )
    )
    return UnderstandingProviderChain(cloud=None, local=None, rule=provider)


# ---------------------------------------------------------------- source gates

def test_run_requires_v31_discriminator(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.0",
            "session_id": session_id,
            "inputs": [
                {
                    "source_id": document_id,
                    "source_type": "document",
                    "processing_status": "ready",
                    "text": "旧版本文本",
                    "captured_at": "2026-08-01T00:00:00Z",
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SCHEMA_VERSION"


def test_run_rejects_stale_input_revision(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 1),  # stale: now 2
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_run_rejects_inactive_document(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, _document_id = _prepare_with_document(token, db_session_factory)
    forged = f"doc_{uuid.uuid4().hex}"

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(
            session_id, forged, 2, source_id=forged
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_NOT_ACTIVE"


def test_run_rejects_discarded_document(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    discard = client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={
            **_headers(token),
            "Idempotency-Key": f"mk-discard-{uuid.uuid4().hex}",
        },
        json={"action": "discard_document", "expected_input_revision": 2},
    )
    assert discard.status_code == 200

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 3),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_NOT_ACTIVE"


def test_run_rejects_document_without_valid_ocr(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(
        token, db_session_factory, ocr_text="   ", status="ocr_failed"
    )

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 2),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_NO_VALID_TEXT"


def test_run_rejects_ocr_error_code_even_with_uploaded_status(monkeypatch, db_session_factory):
    # The upload API keeps Document.status='uploaded' even when OCR fails,
    # so the authoritative OCR record (error_code) must gate the run.
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(
        token,
        db_session_factory,
        status="uploaded",
        ocr_text="残留文本",
        ocr_confidence="low",
        ocr_error_code="OCR_ENGINE_UNAVAILABLE",
    )

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 2),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_OCR_FAILED"


def test_run_rejects_missing_ocr_confidence_and_result(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(
        token,
        db_session_factory,
        status="uploaded",
        ocr_text="残留文本",
        ocr_confidence=None,
        ocr_error_code=None,
        ocr_result_json=None,
    )

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 2),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_OCR_FAILED"


def test_run_accepts_narrative_source(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "session_id": session_id,
            "expected_input_revision": 1,
            "inputs": [
                {
                    "source_id": f"nar_{uuid.uuid4().hex}",
                    "source_type": "narrative",
                    "processing_status": "ready",
                    "text": "最近入睡困难，白天没什么精神。",
                    "captured_at": "2026-08-01T00:00:00Z",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert understanding["case_summary"] is not None
    assert len(understanding["normalized_facts"]) == 1


def test_run_rejects_narrative_without_text(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "session_id": session_id,
            "expected_input_revision": 1,
            "inputs": [
                {
                    "source_id": f"nar_{uuid.uuid4().hex}",
                    "source_type": "narrative",
                    "processing_status": "ready",
                    "text": "   ",
                    "captured_at": "2026-08-01T00:00:00Z",
                }
            ],
        },
    )
    assert response.status_code == 422
    # Blank narrative text is rejected at schema level by NonEmptyString
    # before it can reach the Provider.
    assert response.json()["error"]["code"] == "INVALID_UNDERSTANDING_REQUEST"


def test_run_rejects_voice_transcript_as_not_enabled(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id = _create_flow_session(token)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "session_id": session_id,
            "expected_input_revision": 1,
            "inputs": [
                {
                    "source_id": f"voice_{uuid.uuid4().hex}",
                    "source_type": "voice_transcript",
                    "processing_status": "ready",
                    "text": "伪造的语音转写文本",
                    "captured_at": "2026-08-01T00:00:00Z",
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VOICE_TRANSCRIPT_NOT_ENABLED"


def test_run_rejects_empty_provider_facts(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", lambda: _mock_chain(facts=[])
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 2),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_FACTS_EXTRACTED"
    assert "retry" in response.json()["error"]["next_actions"]


def test_run_rejects_source_not_ready(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(
            session_id, document_id, 2, processing_status="processing"
        ),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_NOT_READY"


# ------------------------------------------------------------------ run + confirm

def test_run_requires_approved_medical_assets(monkeypatch, db_session_factory):
    monkeypatch.setattr(understanding_router, "_resolve_provider_chain", lambda: None)
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    response = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 2),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MEDICAL_ASSET_UNAVAILABLE"


def test_run_produces_editable_case_summary_and_plain_confirm(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)

    created = client.post(
        "/api/v3/understandings",
        headers=_headers(token),
        json=_understanding_run_body(session_id, document_id, 2),
    )
    assert created.status_code == 201, created.text
    understanding = _v3_data(created)
    understanding_id = understanding["understanding_id"]
    assert understanding["schema_version"] == "understanding_v3.1"
    assert understanding["revision"] == 1
    assert understanding["status"] == "needs_confirmation"
    assert understanding["safety_policy"] == "deferred_v3"
    assert understanding["safety_status"] is None
    assert len(understanding["normalized_facts"]) == 1

    # P0-4: a confirmable, editable CaseSummary must exist for the
    # "请确认资料摘要" page.
    case_summary = understanding["case_summary"]
    assert case_summary is not None
    assert case_summary["status"] == "needs_confirmation"
    assert case_summary["revision"] == 1
    assert document_id in case_summary["source_document_ids"]
    # P1-4: public summary uses Chinese copy, never internal enums.
    assert "中度" in case_summary["summary"]
    assert "moderate" not in case_summary["summary"]
    assert "sleep_unrefreshing" not in case_summary["summary"]
    assert any(
        field["field_id"] == "summary" and field["required"]
        for field in case_summary["editable_fields"]
    )

    fetched = client.get(
        f"/api/v3/understandings/{understanding_id}",
        headers=_headers(token),
    )
    assert fetched.status_code == 200
    assert _v3_data(fetched)["revision"] == 1

    confirmed = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 2,
            "decision": "confirm",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    result = _v3_data(confirmed)
    assert result["previous_revision"] == 1
    assert result["revision"] == 2
    assert result["status"] == "confirmed"

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    assert latest["revision"] == 2
    assert latest["status"] == "confirmed"

    activity = _v3_data(
        client.get(
            f"/api/v3/sessions/{session_id}/activity",
            headers=_headers(token),
        )
    )
    assert activity["understanding_ref"] == {
        "understanding_id": understanding_id,
        "revision": 2,
    }
    assert activity["input_revision"] == 3


def test_confirm_revision_and_input_revision_conflicts(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id, document_id, 2),
        )
    )["understanding_id"]

    client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 2,
            "decision": "confirm",
        },
    )
    second = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 2,
            "expected_input_revision": 3,
            "decision": "confirm",
        },
    )
    assert second.status_code == 200

    stale_revision = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 2,
            "expected_input_revision": 4,
            "decision": "confirm",
        },
    )
    assert stale_revision.status_code == 409
    assert stale_revision.json()["error"]["code"] == "REVISION_CONFLICT"

    stale_input = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 3,
            "expected_input_revision": 3,
            "decision": "confirm",
        },
    )
    assert stale_input.status_code == 409
    assert stale_input.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_structured_change_applies_whitelist_and_marks_user_correction(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)
    understanding = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id, document_id, 2),
        )
    )
    understanding_id = understanding["understanding_id"]
    fact_id = understanding["normalized_facts"][0]["fact_id"]

    rejected = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 2,
            "decision": "confirm_with_changes",
            "changes": [
                {
                    "target_type": "normalized_fact",
                    "target_id": fact_id,
                    "field": "claim_code",
                    "old_value": "sleep_unrefreshing",
                    "new_value": "other_claim",
                }
            ],
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "CHANGE_NOT_ALLOWED"

    accepted = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 2,
            "decision": "confirm_with_changes",
            "changes": [
                {
                    "target_type": "normalized_fact",
                    "target_id": fact_id,
                    "field": "negated",
                    "old_value": False,
                    "new_value": True,
                }
            ],
        },
    )
    assert accepted.status_code == 200, accepted.text
    result = _v3_data(accepted)
    assert result["revision"] == 2
    assert fact_id in result["affected_fact_ids"]

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    updated_fact = latest["normalized_facts"][0]
    assert updated_fact["negated"] is True
    assert updated_fact["confirmation_status"] == "confirmed"
    assert updated_fact["extraction"]["method"] == "user_correction"


def test_full_text_edit_without_provider_is_503_and_preserves_snapshot(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id, document_id, 2),
        )
    )["understanding_id"]

    monkeypatch.setattr(understanding_router, "_resolve_provider_chain", lambda: None)
    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 2,
            "decision": "confirm_with_changes",
            "edited_summary_text": "近期睡眠尚可，无特殊不适。",
            "reprocess_requested": True,
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MEDICAL_ASSET_UNAVAILABLE"

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    assert latest["revision"] == 1  # old snapshot unchanged
    assert latest["status"] == "needs_confirmation"


def test_full_text_edit_with_provider_updates_facts_and_summary(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id, document_id, 2),
        )
    )["understanding_id"]

    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 2,
            "decision": "confirm_with_changes",
            "edited_summary_text": "资料中提到最近入睡较慢，白天有些疲惫。",
            "reprocess_requested": True,
        },
    )
    assert response.status_code == 200, response.text
    result = _v3_data(response)
    assert result["revision"] == 2

    latest = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=_headers(token),
        )
    )
    assert latest["status"] == "confirmed"
    assert latest["case_summary"]["summary"] == "资料中提到最近入睡较慢，白天有些疲惫。"
    assert latest["case_summary"]["status"] == "confirmed"
    assert len(latest["normalized_facts"]) == 1
    assert (
        latest["normalized_facts"][0]["source_refs"][0]["source_type"]
        == "user_correction"
    )


def test_confirmation_requires_v31_discriminator(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id, document_id, 2),
        )
    )["understanding_id"]

    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers=_headers(token),
        json={
            "schema_version": "understanding_v3.0",
            "expected_revision": 1,
            "decision": "confirm",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SCHEMA_VERSION"


def test_cross_user_understanding_read_returns_404(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_router, "_resolve_provider_chain", _mock_chain
    )
    token = _guest_token()
    session_id, document_id = _prepare_with_document(token, db_session_factory)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers=_headers(token),
            json=_understanding_run_body(session_id, document_id, 2),
        )
    )["understanding_id"]

    stranger = _guest_token()
    response = client.get(
        f"/api/v3/understandings/{understanding_id}",
        headers=_headers(stranger),
    )
    assert response.status_code == 404

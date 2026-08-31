"""AI fact extraction through the Understanding Provider Chain.

Wires the Issue #89 approved claim dictionary + provider into ingestion:
OCR/Narrative text -> NormalizedFacts; confirmation propagates to inner
state; full-text edits re-extract facts; an unavailable provider never
fabricates facts or a fake revision.
"""

import uuid

from fastapi.testclient import TestClient
import pytest

from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    UnderstandingProviderChain,
)
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.v3.identity import UserIdentity
from backend.app.schemas.v3.understanding import (
    TextSpan,
    UnderstandingProviderFact,
    UnderstandingProviderResponse,
)
from backend.app.services.v3 import understanding_service


client = TestClient(app)


def _v3_data(response):
    return response.json()["data"]


def _guest_headers():
    token = _v3_data(client.post("/api/v3/auth/guest"))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_guest():
    headers = _guest_headers()
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"sess-{uuid.uuid4().hex}"},
        json={},
    )
    session_id = _v3_data(response)["session_id"]
    return headers, session_id


def _seed_document(db_session, *, user_pk, session_id, ocr_text):
    document_id = f"doc_{uuid.uuid4().hex}"
    db_session.add(
        Document(
            user_id=user_pk,
            session_id=session_id,
            document_id=document_id,
            original_filename="sample.png",
            file_type="png",
            file_size_bytes=1024,
            storage_path=f"docs/{document_id}",
            status="uploaded",
            ocr_text=ocr_text,
            ocr_confidence="high",
            ocr_error_code=None,
        )
    )
    db_session.commit()
    return document_id


def _user_pk(db_session, headers):
    token = headers["Authorization"].split(" ")[1]
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    import base64
    import json

    public_user_id = json.loads(base64.urlsafe_b64decode(payload))["sub"]
    identity = (
        db_session.query(UserIdentity)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    return identity.internal_user_pk


def _mock_fact():
    return UnderstandingProviderFact(
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


def _mock_chain(*, facts=None):
    if facts is None:
        facts = [_mock_fact()]
    provider = MockUnderstandingProvider(
        UnderstandingProviderResponse(status="success", facts=facts, warnings=[])
    )
    return UnderstandingProviderChain(cloud=None, local=None, rule=provider)


def _document_source(document_id):
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "document",
        "processing_status": "ready",
        "text_ref": document_id,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _narrative_source(text):
    return {
        "source_id": f"src_{uuid.uuid4().hex}",
        "source_type": "narrative",
        "processing_status": "ready",
        "text": text,
        "captured_at": "2026-01-01T00:00:00Z",
    }


def _run_body(session_id, inputs):
    return {
        "schema_version": "understanding_v3.0",
        "session_id": session_id,
        "inputs": inputs,
    }


def _post(headers, session_id, inputs):
    return client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": f"und-{uuid.uuid4().hex}"},
        json=_run_body(session_id, inputs),
    )


def _confirm(headers, understanding_id, *, decision="confirm", **extra):
    body = {
        "schema_version": "understanding_v3.0",
        "expected_revision": 1,
        "decision": decision,
    }
    body.update(extra)
    return client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"cfm-{uuid.uuid4().hex}"},
        json=body,
    )


def test_document_extraction_produces_normalized_facts(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert len(understanding["normalized_facts"]) == 1
    fact = understanding["normalized_facts"][0]
    assert fact["fact_code"] == "sleep_unrefreshing"
    assert fact["value"]["value"] == "moderate"
    assert fact["negated"] is False
    assert fact["subject"] == "self"
    assert fact["confirmation_status"] == "unconfirmed"
    assert fact["extraction"]["method"] == "rule"
    assert fact["source_refs"][0]["source_type"] == "document"


def test_narrative_extraction_source_ref_is_narrative(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()

    response = _post(headers, session_id, [_narrative_source("最近总是睡不好。")])
    assert response.status_code == 201, response.text
    understanding = _v3_data(response)
    assert len(understanding["normalized_facts"]) == 1
    assert (
        understanding["normalized_facts"][0]["source_refs"][0]["source_type"]
        == "narrative"
    )
    # narrative-only: no material CaseSummary / no document-confirmation page
    assert understanding["case_summary"] is None


def test_confirm_propagates_to_facts_and_case_summary(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    confirmed = _confirm(headers, understanding_id)
    assert confirmed.status_code == 201, confirmed.text
    result = _v3_data(confirmed)
    assert result["revision"] == 2

    read = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=headers,
        )
    )
    assert read["status"] == "confirmed"
    assert read["revision"] == 2
    assert all(
        fact["confirmation_status"] == "confirmed"
        for fact in read["normalized_facts"]
    )
    assert read["case_summary"]["status"] == "confirmed"
    assert read["case_summary"]["revision"] == 2


def test_provider_unavailable_never_fabricates_facts(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: None
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    response = _post(headers, session_id, [_document_source(document_id)])
    assert response.status_code == 201, response.text
    assert _v3_data(response)["normalized_facts"] == []


def test_full_text_edit_re_extracts_facts_via_provider(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: _mock_chain()
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    response = _confirm(
        headers,
        understanding_id,
        decision="confirm_with_changes",
        edited_summary_text="资料中提到最近入睡较慢，白天有些疲惫。",
        reprocess_requested=True,
    )
    assert response.status_code == 201, response.text
    result = _v3_data(response)
    assert result["revision"] == 2
    assert len(result["affected_fact_ids"]) == 1

    read = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=headers,
        )
    )
    fact = read["normalized_facts"][0]
    assert fact["source_refs"][0]["source_type"] == "user_correction"
    assert fact["confirmation_status"] == "confirmed"
    assert read["case_summary"]["summary"] == "资料中提到最近入睡较慢，白天有些疲惫。"


def test_full_text_edit_without_provider_keeps_old_revision(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: None
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db, user_pk=user_pk, session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足。",
    )
    db.close()

    understanding_id = _v3_data(
        _post(headers, session_id, [_document_source(document_id)])
    )["understanding_id"]

    response = _confirm(
        headers,
        understanding_id,
        decision="confirm_with_changes",
        edited_summary_text="资料中提到最近入睡较慢。",
        reprocess_requested=True,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FACT_EXTRACTION_UNAVAILABLE"

    read = _v3_data(
        client.get(
            f"/api/v3/understandings/{understanding_id}",
            headers=headers,
        )
    )
    assert read["revision"] == 1  # old snapshot preserved
    assert read["status"] == "needs_confirmation"

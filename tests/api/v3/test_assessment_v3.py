"""Agent 1 Assessment V3 — deterministic aggregation over approved assets."""

import base64
import json
import uuid

from fastapi.testclient import TestClient

from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    UnderstandingProviderChain,
)
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.models.v3.assessment import AssessmentV3
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.session import V3IdempotencyRecord
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


def _user_pk(db_session, headers):
    token = headers["Authorization"].split(" ")[1]
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    public_user_id = json.loads(base64.urlsafe_b64decode(payload))["sub"]
    identity = (
        db_session.query(UserIdentity)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    return identity.internal_user_pk


def _setup_guest():
    headers = _guest_headers()
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"sess-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    return headers, _v3_data(response)["session_id"]


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


def _provider_fact(claim_code, display_name, category):
    return UnderstandingProviderFact(
        claim_code=claim_code,
        display_name=display_name,
        category=category,
        value={"type": "frequency_0_4", "value": 3},
        time_window="past_7_days",
        negated=False,
        subject="self",
        span=TextSpan(start=0, end=6),
        extraction_confidence=0.8,
    )


def _mock_chain(facts):
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


def _confirmed_understanding(headers, session_id, db_session, facts):
    """Create + confirm an understanding carrying the given provider facts."""
    user_pk = _user_pk(db_session, headers)
    document_id = _seed_document(
        db_session,
        user_pk=user_pk,
        session_id=session_id,
        ocr_text="近期入睡困难，白天精神不足，胸胁不舒。",
    )
    run = client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": f"und-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.0",
            "session_id": session_id,
            "inputs": [_document_source(document_id)],
        },
    )
    assert run.status_code == 201, run.text
    understanding_id = _v3_data(run)["understanding_id"]
    confirm = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": f"cfm-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 1,
            "decision": "confirm",
        },
    )
    assert confirm.status_code == 201, confirm.text
    return understanding_id


def _assessment_body(session_id, understanding_id, expected_input_revision):
    return {
        "schema_version": "assessment_v3.1",
        "session_id": session_id,
        "expected_input_revision": expected_input_revision,
        "understanding_ref": {
            "understanding_id": understanding_id,
            "revision": 2,
        },
        "questionnaire_ref": None,
    }


def _assessment_count(db_session_factory, headers):
    db = db_session_factory()
    try:
        user_pk = _user_pk(db, headers)
        return (
            db.query(AssessmentV3)
            .filter(AssessmentV3.internal_user_pk == user_pk)
            .count()
        )
    finally:
        db.close()


def test_assessment_available_from_two_liver_claims(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [
                _provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state"),
                _provider_fact("flank_discomfort", "胁肋不适", "somatic"),
            ]
        ),
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    understanding_id = _confirmed_understanding(
        headers, session_id, db, facts=None
    )
    db.close()

    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=_assessment_body(session_id, understanding_id, 2),
    )
    assert response.status_code == 201, response.text
    assessment = _v3_data(response)
    assert assessment["schema_version"] == "assessment_v3.1"
    assert assessment["status"] == "needs_confirmation"
    assert assessment["safety_status"] is None
    assert assessment["flow_contract_version"] == "v3-owner-flow-1"
    assert assessment["organ_profile"]["status"] == "available"
    weights = assessment["organ_profile"]["weights"]
    assert set(weights) == {"liver", "heart", "spleen", "lung", "kidney"}
    assert abs(sum(weights.values()) - 1.0) < 0.001
    assert assessment["organ_profile"]["weights"]["liver"] > 0
    assert len(assessment["fact_evidence"]) == 2
    assert len(assessment["organ_evidence_links"]) == 2
    assert "goal_summary" not in assessment["presentation"]


def test_assessment_insufficient_single_claim(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    understanding_id = _confirmed_understanding(
        headers, session_id, db, facts=None
    )
    db.close()

    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=_assessment_body(session_id, understanding_id, 2),
    )
    assert response.status_code == 201, response.text
    assessment = _v3_data(response)
    # single claim cannot satisfy min_count=2 -> honest insufficient profile
    assert assessment["organ_profile"]["status"] == "insufficient"
    assert assessment["organ_profile"]["weights"] is None
    assert assessment["degradation"]["active"] is True
    assert "INSUFFICIENT_EVIDENCE" in assessment["degradation"]["reason_codes"]


def test_assessment_replays_same_key_and_payload_without_duplicate(
    monkeypatch, db_session_factory
):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    understanding_id = _confirmed_understanding(headers, session_id, db, facts=None)
    db.close()

    body = _assessment_body(session_id, understanding_id, 2)
    key = f"asmt-replay-{uuid.uuid4().hex}"
    first = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )
    replay = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 200, replay.text
    assert _v3_data(replay) == _v3_data(first)
    assert _v3_data(replay)["assessment_id"] == _v3_data(first)["assessment_id"]
    assert _assessment_count(db_session_factory, headers) == 1

    db = db_session_factory()
    try:
        records = (
            db.query(V3IdempotencyRecord)
            .filter(
                V3IdempotencyRecord.internal_user_pk
                == _user_pk(db, headers),
                V3IdempotencyRecord.idempotency_key == key,
            )
            .all()
        )
        assert len(records) == 1
        assert records[0].status == "succeeded"
        assert records[0].operation == "create_v3_assessment"
    finally:
        db.close()


def test_assessment_reused_key_with_different_payload_conflicts_without_duplicate(
    monkeypatch, db_session_factory
):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    understanding_id = _confirmed_understanding(headers, session_id, db, facts=None)
    db.close()

    key = f"asmt-conflict-{uuid.uuid4().hex}"
    first_body = _assessment_body(session_id, understanding_id, 2)
    conflict_body = _assessment_body(session_id, understanding_id, 1)
    first = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": key},
        json=first_body,
    )
    conflict = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": key},
        json=conflict_body,
    )

    assert first.status_code == 201, first.text
    assert conflict.status_code == 422, conflict.text
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _assessment_count(db_session_factory, headers) == 1


def test_assessment_requires_confirmed_understanding(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    document_id = _seed_document(
        db,
        user_pk=user_pk,
        session_id=session_id,
        ocr_text="近期入睡困难。",
    )
    run = client.post(
        "/api/v3/understandings",
        headers={**headers, "Idempotency-Key": f"und-{uuid.uuid4().hex}"},
        json={
            "schema_version": "understanding_v3.0",
            "session_id": session_id,
            "inputs": [_document_source(document_id)],
        },
    )
    assert run.status_code == 201
    understanding_id = _v3_data(run)["understanding_id"]  # NOT confirmed
    db.close()

    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=_assessment_body(session_id, understanding_id, 1),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSESSMENT_INPUT_NOT_READY"


def test_assessment_without_document_requires_questionnaire(monkeypatch, db_session_factory):
    monkeypatch.setattr(
        understanding_service, "build_provider_chain", lambda: None
    )
    headers, session_id = _setup_guest()
    db = db_session_factory()
    del db

    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json={
            "schema_version": "assessment_v3.1",
            "session_id": session_id,
            "expected_input_revision": 1,
            "understanding_ref": None,
            "questionnaire_ref": None,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSESSMENT_INPUT_NOT_READY"

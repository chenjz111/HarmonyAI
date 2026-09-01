"""Agent 2 Diagnosis V3 — honest abstain / degraded RAG, no fabricated
syndromes without an approved syndrome whitelist."""

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import event, null

from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import AssessmentRevisionV3, AssessmentV3
from backend.app.models.v3.diagnosis import AiProviderRun, DiagnosisRun, RagRetrievalRun
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.session import V3IdempotencyRecord


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


def _setup_flow_session(db_session, headers):
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"sess-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    session_id = _v3_data(response)["session_id"]
    user_pk = _user_pk(db_session, headers)
    row = (
        db_session.query(SessionModel)
        .filter(SessionModel.session_id == session_id)
        .one()
    )
    return session_id, user_pk, row


def _seed_confirmed_assessment(
    db_session,
    *,
    user_pk,
    session_row,
    organ_profile_json,
    assessment_id=None,
    assessment_status="confirmed",
    confirmation_status="confirmed",
    current_revision=1,
    assessment_input_revision=1,
    revision_input_revision=1,
):
    if assessment_id is None:
        assessment_id = f"asmt_{uuid.uuid4().hex}"
    db_session.add(
        AssessmentV3(
            assessment_id=assessment_id,
            internal_user_pk=user_pk,
            session_row_id=session_row.id,
            understanding_id=None,
            understanding_revision=None,
            questionnaire_submission_id=None,
            current_revision=current_revision,
            status=assessment_status,
            safety_status=None,
            user_goal_json=null(),
            flow_contract_version="v3-owner-flow-1",
            input_revision=assessment_input_revision,
            input_mode="without_document",
            safety_policy="deferred_v3",
            safety_evaluation_status="not_run",
        )
    )
    db_session.add(
        AssessmentRevisionV3(
            assessment_id=assessment_id,
            revision=current_revision,
            previous_revision=None,
            understanding_revision=1,
            input_revision=revision_input_revision,
            status=assessment_status,
            confirmation_status=confirmation_status,
            state_summary="测试评估",
            recent_context_summary="",
            organ_profile_json=organ_profile_json,
            evidence_coverage=0.5,
            source_diversity=1,
            conflicts_json=[],
            missing_information_json=[],
            degradation_json={"active": False, "reason_codes": []},
            presentation_json={},
        )
    )
    db_session.commit()
    return assessment_id


def _diagnosis_body(session_id, assessment_id, input_revision):
    return {
        "schema_version": "diagnosis_v3.1",
        "session_id": session_id,
        "diagnosis_id": f"diag_{uuid.uuid4().hex}",
        "assessment_ref": {
            "assessment_id": assessment_id,
            "revision": 1,
            "confirmation_status": "confirmed",
            "flow_contract_version": "v3-owner-flow-1",
            "input_revision": input_revision,
            "safety_policy": "deferred_v3",
            "safety_status": None,
        },
        "organ_profile": {"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
        "fact_evidence": [],
        "organ_evidence_links": [],
        "conflicts": [],
        "missing_information": [],
    }


def test_diagnosis_abstains_when_element_evidence_insufficient(db_session_factory):
    headers = _guest_headers()
    db = db_session_factory()
    _session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"diag-{uuid.uuid4().hex}"},
        json=_diagnosis_body(_session_id, assessment_id, 1),
    )
    assert response.status_code == 201, response.text
    result = response.json()["data"]
    # honest abstain, never fabricated syndromes
    assert result["status"] == "abstained"
    assert result["abstained"] is True
    assert result["element_profile"]["status"] == "insufficient"
    assert result["candidate_tendencies"] == []
    # RAG ingestion is not approved -> degraded marker, no fake hits
    assert result["degradation"]["active"] is True
    assert "RAG_INGESTION_NOT_APPROVED" in result["degradation"]["reason_codes"]
    assert "不构成医学诊断或治疗建议" in result["presentation"]["disclaimer"]


def test_diagnosis_reports_asset_unavailable_when_syndrome_whitelist_missing(
    db_session_factory,
):
    headers = _guest_headers()
    db = db_session_factory()
    _session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.4,
                "heart": 0.2,
                "spleen": 0.2,
                "lung": 0.1,
                "kidney": 0.1,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"diag-{uuid.uuid4().hex}"},
        json=_diagnosis_body(_session_id, assessment_id, 1),
    )
    # Element evidence exists but no approved syndrome whitelist: must not
    # fabricate a syndrome — report the medical asset as unavailable.
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MEDICAL_ASSET_UNAVAILABLE"
    assert response.json()["error"]["retryable"] is False
    db = db_session_factory()
    try:
        assert db.query(DiagnosisRun).count() == 0
        assert db.query(AiProviderRun).count() == 0
        assert db.query(RagRetrievalRun).count() == 0
    finally:
        db.close()


def test_diagnosis_rejects_assessment_from_another_user(db_session_factory):
    owner_headers = _guest_headers()
    stranger_headers = _guest_headers()
    db = db_session_factory()
    owner_session_id, owner_pk, owner_session = _setup_flow_session(db, owner_headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=owner_pk,
        session_row=owner_session,
        organ_profile_json={"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**stranger_headers, "Idempotency-Key": "diag-cross-user"},
        json=_diagnosis_body(owner_session_id, assessment_id, 1),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    db = db_session_factory()
    try:
        assert db.query(DiagnosisRun).count() == 0
    finally:
        db.close()


def test_diagnosis_rejects_assessment_from_another_session(db_session_factory):
    headers = _guest_headers()
    db = db_session_factory()
    owner_session_id, user_pk, owner_session = _setup_flow_session(db, headers)
    other_session_id, _, _ = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=owner_session,
        organ_profile_json={"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": "diag-cross-session"},
        json=_diagnosis_body(other_session_id, assessment_id, 1),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    db = db_session_factory()
    try:
        assert db.query(DiagnosisRun).count() == 0
    finally:
        db.close()


def test_diagnosis_rejects_mismatched_assessment_revision(db_session_factory):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        current_revision=2,
        organ_profile_json={"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": "diag-revision-mismatch"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_diagnosis_rejects_mismatched_input_revision(db_session_factory):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        assessment_input_revision=2,
        revision_input_revision=2,
        organ_profile_json={"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": "diag-input-revision-mismatch"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_diagnosis_rejects_unconfirmed_assessment(db_session_factory):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        assessment_status="needs_confirmation",
        confirmation_status="unconfirmed",
        organ_profile_json={"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
    )
    db.close()

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": "diag-unconfirmed"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_diagnosis_replay_and_conflict_do_not_duplicate_records(db_session_factory):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={"status": "insufficient", "weights": None, "score_semantics": "relative_evidence_distribution"},
    )
    db.close()

    key = "diag-replay-and-conflict"
    body = _diagnosis_body(session_id, assessment_id, 1)
    first = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )
    replay = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )
    conflict_body = {**body, "diagnosis_id": "diag-different"}
    conflict = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": key},
        json=conflict_body,
    )

    assert first.status_code == 201, first.text
    assert replay.status_code == 200, replay.text
    assert _v3_data(replay) == _v3_data(first)
    assert conflict.status_code == 422, conflict.text
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    db = db_session_factory()
    try:
        assert db.query(DiagnosisRun).count() == 1
        records = (
            db.query(V3IdempotencyRecord)
            .filter(V3IdempotencyRecord.idempotency_key == key)
            .all()
        )
        assert len(records) == 1
        assert records[0].status == "succeeded"
        assert records[0].operation == "create_v3_diagnosis"
    finally:
        db.close()


def test_diagnosis_concurrent_same_key_replays_without_duplicate(
    concurrent_api_database,
):
    session_factory, engine = concurrent_api_database
    headers = _guest_headers()
    db = session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    body = _diagnosis_body(session_id, assessment_id, 1)
    key = f"diag-concurrent-{uuid.uuid4().hex}"
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    lookup_count = 0

    def synchronize_initial_lookups(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ):
        nonlocal lookup_count
        if "idempotency_records" not in statement.lower():
            return
        with lock:
            lookup_count += 1
            should_wait = lookup_count <= 2
        if should_wait:
            barrier.wait(timeout=10)

    event.listen(engine, "after_cursor_execute", synchronize_initial_lookups)
    try:
        def post_diagnosis():
            return client.post(
                "/api/v3/diagnoses",
                headers={**headers, "Idempotency-Key": key},
                json=body,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: post_diagnosis(), range(2)))
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_initial_lookups)

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert _v3_data(responses[0]) == _v3_data(responses[1])
    db = session_factory()
    try:
        assert db.query(DiagnosisRun).count() == 1
        records = (
            db.query(V3IdempotencyRecord)
            .filter(V3IdempotencyRecord.idempotency_key == key)
            .all()
        )
        assert len(records) == 1
        assert records[0].status == "succeeded"
    finally:
        db.close()


def test_diagnosis_concurrent_different_payload_returns_idempotency_conflict(
    concurrent_api_database,
):
    session_factory, engine = concurrent_api_database
    headers = _guest_headers()
    db = session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    first_body = _diagnosis_body(session_id, assessment_id, 1)
    second_body = {**first_body, "diagnosis_id": "diag-concurrent-different"}
    key = f"diag-concurrent-conflict-{uuid.uuid4().hex}"
    bodies = [first_body, second_body]
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    lookup_count = 0

    def synchronize_initial_lookups(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ):
        nonlocal lookup_count
        if "idempotency_records" not in statement.lower():
            return
        with lock:
            lookup_count += 1
            should_wait = lookup_count <= 2
        if should_wait:
            barrier.wait(timeout=10)

    event.listen(engine, "after_cursor_execute", synchronize_initial_lookups)
    try:
        def post_diagnosis(body):
            return client.post(
                "/api/v3/diagnoses",
                headers={**headers, "Idempotency-Key": key},
                json=body,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(post_diagnosis, bodies))
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_initial_lookups)

    assert sorted(response.status_code for response in responses) == [201, 422]
    conflict = next(response for response in responses if response.status_code == 422)
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    db = session_factory()
    try:
        assert db.query(DiagnosisRun).count() == 1
        records = (
            db.query(V3IdempotencyRecord)
            .filter(V3IdempotencyRecord.idempotency_key == key)
            .all()
        )
        assert len(records) == 1
    finally:
        db.close()

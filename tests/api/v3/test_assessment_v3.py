"""Agent 1 Assessment V3 — deterministic aggregation over approved assets."""

import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import event

from backend.ai_engine.v3.understanding_provider import (
    MockUnderstandingProvider,
    UnderstandingProviderChain,
)
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.assessment import AssessmentV3
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.session import V3IdempotencyRecord
from backend.app.models.v3.understanding import QuestionnaireSubmissionV3
from backend.app.schemas.v3.understanding import (
    TextSpan,
    UnderstandingProviderFact,
    UnderstandingProviderResponse,
)
from backend.app.schemas.v3.assessment import FactEvidence
from backend.app.services.v3 import assessment_service, understanding_service
from backend.app.services.v3.knowledge_assets import load_organ_mapping


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


def _seed_questionnaire(db, *, headers, session_id, answers):
    user_pk = _user_pk(db, headers)
    session_row = (
        db.query(SessionModel)
        .filter(SessionModel.session_id == session_id)
        .one()
    )
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "knowledge"
            / "v3"
            / "questionnaire-v3.0.json"
        ).read_text(encoding="utf-8")
    )
    submission = QuestionnaireSubmissionV3(
        questionnaire_submission_id=f"qsub_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row.id,
        schema_id=manifest["schema_id"],
        schema_version=manifest["schema_version"],
        manifest_version=manifest["manifest_version"],
        content_checksum=manifest["content_checksum"],
        time_window_days=7,
        answers_json=answers,
        idempotency_key=f"qsub-{uuid.uuid4().hex}",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    db.commit()
    return submission.questionnaire_submission_id, manifest


def _aggregation_fact(claim_code, source_id, *, source_type="document", value=None):
    return FactEvidence(
        fact_evidence_id=f"fev_{uuid.uuid4().hex}",
        assessment_id="asmt_aggregation",
        assessment_revision=1,
        fact_id=f"fact_{uuid.uuid4().hex}",
        claim_code=claim_code,
        display_name=claim_code,
        category="test",
        value=value or {"type": "severity", "value": "moderate"},
        time_window="past_7_days",
        direction="supporting",
        reliability=1.0,
        source_refs=[{"source_id": source_id, "source_type": source_type}],
        confirmation_status="confirmed",
    )


def test_assessment_uses_approved_multi_organ_links():
    evidence = [_aggregation_fact("sleep_disturbance", "source-sleep")]

    links = assessment_service._organ_links(evidence, load_organ_mapping())

    assert {
        (link.organ.value, link.mapping_rule_id)
        for link in links
    } == {
        ("heart", "map_sleep_disturbance_heart_multi_01"),
        ("spleen", "map_sleep_disturbance_spleen_multi_01"),
        ("kidney", "map_sleep_disturbance_kidney_multi_01"),
    }


def test_assessment_applies_sleep_conflict_rule_once_per_source():
    mapping = load_organ_mapping()
    base = [
        _aggregation_fact("anger_tendency", "source-liver"),
        _aggregation_fact("flank_discomfort", "source-liver"),
        _aggregation_fact("agitation_tendency", "source-heart"),
        _aggregation_fact("palpitation_at_rest", "source-heart"),
    ]
    base_links = assessment_service._organ_links(base, mapping)
    one_sleep = base + [_aggregation_fact("sleep_disturbance", "source-sleep")]
    two_sleep = one_sleep + [_aggregation_fact("unrefreshing_sleep", "source-sleep")]

    one_links = assessment_service._organ_links(one_sleep, mapping)
    two_links = assessment_service._organ_links(two_sleep, mapping)
    one_weights = assessment_service._organ_weights(one_sleep, one_links, mapping)
    two_weights = assessment_service._organ_weights(two_sleep, two_links, mapping)
    base_weights = assessment_service._organ_weights(base, base_links, mapping)

    assert one_weights != base_weights
    assert one_weights == two_weights


def test_assessment_marks_questionnaire_priority_conflict_without_raw_text():
    evidence = [
        _aggregation_fact(
            "anger_tendency",
            "source-document",
            value={"type": "severity", "value": "mild"},
        ),
        _aggregation_fact(
            "anger_tendency",
            "qsub-priority",
            source_type="questionnaire",
            value={"type": "severity", "value": "severe"},
        ),
    ]

    conflicts = assessment_service._build_conflicts(evidence, load_organ_mapping())

    assert len(conflicts) == 1
    assert conflicts[0].severity == "minor"
    assert conflicts[0].resolution_status == "unresolved"
    assert "source-document" not in conflicts[0].display_summary
    assert "qsub-priority" not in conflicts[0].display_summary


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


def test_assessment_rejects_understanding_from_another_session(
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
    first_understanding_id = _confirmed_understanding(
        headers, session_id, db, facts=None
    )
    db.close()

    second_session_response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"sess-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert second_session_response.status_code == 201, second_session_response.text
    second_session_id = _v3_data(second_session_response)["session_id"]
    db = db_session_factory()
    second_understanding_id = _confirmed_understanding(
        headers, second_session_id, db, facts=None
    )
    db.close()

    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=_assessment_body(session_id, second_understanding_id, 2),
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "ASSESSMENT_INPUT_NOT_READY"
    assert _assessment_count(db_session_factory, headers) == 0


def test_assessment_rejects_understanding_owned_by_another_user(
    monkeypatch, db_session_factory
):
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    owner_headers, owner_session_id = _setup_guest()
    db = db_session_factory()
    foreign_understanding_id = _confirmed_understanding(
        owner_headers, owner_session_id, db, facts=None
    )
    db.close()

    headers, session_id = _setup_guest()
    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=_assessment_body(session_id, foreign_understanding_id, 1),
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "ASSESSMENT_INPUT_NOT_READY"
    assert _assessment_count(db_session_factory, headers) == 0


def test_assessment_consumes_complete_questionnaire_without_document(
    db_session_factory,
):
    headers, session_id = _setup_guest()
    db = db_session_factory()
    user_pk = _user_pk(db, headers)
    session_row = (
        db.query(SessionModel)
        .filter(SessionModel.session_id == session_id)
        .one()
    )
    from pathlib import Path

    manifest = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "knowledge"
            / "v3"
            / "questionnaire-v3.0.json"
        ).read_text(encoding="utf-8")
    )
    answers = [
        {"question_id": "q01", "answer_type": "frequency_0_4", "value": 3},
        {"question_id": "q02", "answer_type": "frequency_0_4", "value": 0},
        {"question_id": "q03", "answer_type": "frequency_0_4", "value": 0},
        {"question_id": "q04", "answer_type": "frequency_0_4", "value": 0},
        {"question_id": "q05", "answer_type": "frequency_0_4", "value": 0},
        {"question_id": "q06", "answer_type": "multi_choice_evidence", "value": ["flank_discomfort"]},
        {"question_id": "q07", "answer_type": "multi_choice_evidence", "value": ["none"]},
        {"question_id": "q08", "answer_type": "multi_choice_evidence", "value": ["none"]},
        {"question_id": "q09", "answer_type": "multi_choice_evidence", "value": ["none"]},
        {"question_id": "q10", "answer_type": "multi_choice_evidence", "value": ["none"]},
    ]
    submission = QuestionnaireSubmissionV3(
        questionnaire_submission_id=f"qsub_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row.id,
        schema_id=manifest["schema_id"],
        schema_version=manifest["schema_version"],
        manifest_version=manifest["manifest_version"],
        content_checksum=manifest["content_checksum"],
        time_window_days=7,
        answers_json=answers,
        idempotency_key=f"qsub-{uuid.uuid4().hex}",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    session_row.input_mode = "without_document"
    session_row.input_revision = 2
    session_row.active_questionnaire_submission_id = submission.questionnaire_submission_id
    db.commit()
    questionnaire_id = submission.questionnaire_submission_id
    db.close()

    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json={
            "schema_version": "assessment_v3.1",
            "session_id": session_id,
            "expected_input_revision": 2,
            "understanding_ref": None,
            "questionnaire_ref": {
                "questionnaire_submission_id": questionnaire_id,
                "schema_id": manifest["schema_id"],
                "schema_version": manifest["schema_version"],
                "manifest_version": manifest["manifest_version"],
                "content_checksum": manifest["content_checksum"],
            },
        },
    )

    assert response.status_code == 201, response.text
    assessment = _v3_data(response)
    assert assessment["understanding_ref"] is None
    assert len(assessment["fact_evidence"]) == 2
    assert {item["claim_code"] for item in assessment["fact_evidence"]} == {
        "anger_tendency",
        "flank_discomfort",
    }
    assert all(
        item["source_refs"][0]["source_type"] == "questionnaire"
        for item in assessment["fact_evidence"]
    )


def test_assessment_combines_understanding_and_questionnaire_evidence(
    monkeypatch, db_session_factory
):
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
    understanding_id = _confirmed_understanding(headers, session_id, db, facts=None)
    questionnaire_id, manifest = _seed_questionnaire(
        db,
        headers=headers,
        session_id=session_id,
        answers=[
            {"question_id": "q01", "answer_type": "frequency_0_4", "value": 3},
            {"question_id": "q02", "answer_type": "frequency_0_4", "value": 0},
            {"question_id": "q03", "answer_type": "frequency_0_4", "value": 0},
            {"question_id": "q04", "answer_type": "frequency_0_4", "value": 0},
            {"question_id": "q05", "answer_type": "frequency_0_4", "value": 0},
            {"question_id": "q06", "answer_type": "multi_choice_evidence", "value": ["none"]},
            {"question_id": "q07", "answer_type": "multi_choice_evidence", "value": ["none"]},
            {"question_id": "q08", "answer_type": "multi_choice_evidence", "value": ["none"]},
            {"question_id": "q09", "answer_type": "multi_choice_evidence", "value": ["none"]},
            {"question_id": "q10", "answer_type": "multi_choice_evidence", "value": ["none"]},
        ],
    )
    db.close()

    body = _assessment_body(session_id, understanding_id, 2)
    body["questionnaire_ref"] = {
        "questionnaire_submission_id": questionnaire_id,
        "schema_id": manifest["schema_id"],
        "schema_version": manifest["schema_version"],
        "manifest_version": manifest["manifest_version"],
        "content_checksum": manifest["content_checksum"],
    }
    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=body,
    )

    assert response.status_code == 201, response.text
    assessment = _v3_data(response)
    assert len(assessment["fact_evidence"]) == 3
    assert {
        item["source_refs"][0]["source_type"]
        for item in assessment["fact_evidence"]
    } == {"document", "questionnaire"}
    assert assessment["source_diversity"] == 2


def test_assessment_accepts_optional_user_goal_for_music_design(
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
    body["user_goal"] = {
        "primary_goal": "sleep",
        "secondary_goal": "relaxation",
        "custom_goal_text": None,
    }
    response = client.post(
        "/api/v3/assessments",
        headers={**headers, "Idempotency-Key": f"asmt-{uuid.uuid4().hex}"},
        json=body,
    )

    assert response.status_code == 201, response.text
    assessment = _v3_data(response)
    assert assessment["user_goal"]["primary_goal"] == "sleep"
    assert assessment["user_goal"]["secondary_goal"] == "relaxation"
    assert "goal_summary" not in assessment["presentation"]
    db = db_session_factory()
    try:
        row = db.query(AssessmentV3).filter(
            AssessmentV3.assessment_id == assessment["assessment_id"]
        ).one()
        assert row.user_goal_json == body["user_goal"]
    finally:
        db.close()


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


def test_assessment_concurrent_same_key_replays_without_duplicate(
    monkeypatch, concurrent_api_database
):
    session_factory, engine = concurrent_api_database
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    headers, session_id = _setup_guest()
    db = session_factory()
    understanding_id = _confirmed_understanding(headers, session_id, db, facts=None)
    db.close()

    body = _assessment_body(session_id, understanding_id, 2)
    key = f"asmt-concurrent-{uuid.uuid4().hex}"
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
        def post_assessment():
            return client.post(
                "/api/v3/assessments",
                headers={**headers, "Idempotency-Key": key},
                json=body,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: post_assessment(), range(2)))
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_initial_lookups)

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert _v3_data(responses[0]) == _v3_data(responses[1])
    assert _assessment_count(session_factory, headers) == 1


def test_assessment_concurrent_different_payload_returns_idempotency_conflict(
    monkeypatch, concurrent_api_database
):
    session_factory, engine = concurrent_api_database
    monkeypatch.setattr(
        understanding_service,
        "build_provider_chain",
        lambda: _mock_chain(
            [_provider_fact("anger_tendency", "烦躁易怒倾向", "emotional_state")]
        ),
    )
    headers, first_session_id = _setup_guest()
    db = session_factory()
    first_understanding_id = _confirmed_understanding(
        headers, first_session_id, db, facts=None
    )
    db.close()

    second_session_response = client.post(
        "/api/v3/sessions",
        headers={
            **headers,
            "Idempotency-Key": f"sess-{uuid.uuid4().hex}",
        },
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert second_session_response.status_code == 201, second_session_response.text
    second_session_id = _v3_data(second_session_response)["session_id"]
    db = session_factory()
    second_understanding_id = _confirmed_understanding(
        headers, second_session_id, db, facts=None
    )
    db.close()

    key = f"asmt-concurrent-conflict-{uuid.uuid4().hex}"
    bodies = [
        _assessment_body(first_session_id, first_understanding_id, 2),
        _assessment_body(second_session_id, second_understanding_id, 2),
    ]
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
        def post_assessment(body):
            return client.post(
                "/api/v3/assessments",
                headers={**headers, "Idempotency-Key": key},
                json=body,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(post_assessment, bodies))
    finally:
        event.remove(engine, "after_cursor_execute", synchronize_initial_lookups)

    assert sorted(response.status_code for response in responses) == [201, 422]
    conflict = next(response for response in responses if response.status_code == 422)
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _assessment_count(session_factory, headers) == 1


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

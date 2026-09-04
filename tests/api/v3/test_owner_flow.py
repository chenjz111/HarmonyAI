"""Owner Flow Amendment 001 (v3-owner-flow-1) backend tests.

Covers the non-conflicting #79 surface: session flow-contract negotiation,
active-input transitions (select_mode / replace_document / discard_document)
with ownership / idempotency / expected_input_revision, the edited-summary
confirmation path, deferred safety, and the Agent 1/Agent 3 UserGoal boundary.
"""

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import uuid

from fastapi.testclient import TestClient
import pydantic
import pytest

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.document import Document
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.session import SessionInputRevision
from backend.app.models.v3.understanding import (
    NormalizedFact,
    QuestionnaireSubmissionV3,
    UnderstandingRevision,
)
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentRelevanceRecordRequest
from backend.app.services.v3.activity_service import (
    AssessmentInputNotReady,
    validate_assessment_input_readiness,
)
from backend.app.services.v3.document_relevance_service import record_relevance


client = TestClient(app)


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


@contextmanager
def _seed_db():
    generator = app.dependency_overrides[get_db]()
    try:
        yield next(generator)
    finally:
        generator.close()


def _new_flow_session(headers) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"seed-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _legacy_session(headers) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"seed-{uuid.uuid4().hex}"},
        json={},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _seed_document(session, *, user_pk, session_id, ocr_text=None, ocr_error_code=None):
    document_id = f"doc_{uuid.uuid4().hex}"
    session.add(
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
            ocr_confidence="high" if ocr_text else None,
            ocr_error_code=ocr_error_code,
        )
    )
    session.commit()
    return document_id


def _user_pk(session, token: str) -> int:
    public_user_id = _public_user_id(token.split()[1])
    user = (
        session.query(UserIdentity)
        .filter(UserIdentity.public_user_id == public_user_id)
        .one()
    )
    return user.internal_user_pk


def _transition(headers, session_id, idempotency_key, body):
    return client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=body,
    )


def _principal(headers: dict[str, str]) -> AuthPrincipal:
    public_user_id = _public_user_id(headers["Authorization"].split()[1])
    with _seed_db() as session:
        internal_user_pk = (
            session.query(UserIdentity)
            .filter(UserIdentity.public_user_id == public_user_id)
            .one()
            .internal_user_pk
        )
    return AuthPrincipal(
        internal_user_pk=internal_user_pk,
        public_user_id=public_user_id,
        auth_type="guest",
        guest_expires_at="2030-01-01T00:00:00Z",
    )


def _bind_document_set(
    headers: dict[str, str],
    session_id: str,
    document_id: str,
    expected_input_revision: int,
    outcome: str = "VALID",
) -> int:
    response = client.post(
        f"/api/v3/sessions/{session_id}/document-sets",
        headers={**headers, "Idempotency-Key": f"set-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": expected_input_revision,
            "document_ids": [document_id],
        },
    )
    assert response.status_code == 201, response.text
    result = _v3_data(response)
    with _seed_db() as session:
        record_relevance(
            session,
            _principal(headers),
            DocumentRelevanceRecordRequest(
                document_set_id=result["document_set_id"],
                document_set_revision=result["revision"],
                items=[
                    {
                        "document_id": document_id,
                        "outcome": outcome,
                        "reason_codes": [],
                    }
                ],
                evaluator="test",
                evaluator_version="v1",
            ),
        )
    return result["input_revision"]


def _session_row(session_id):
    with _seed_db() as session:
        return session.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()


def test_new_flow_session_binds_contract_and_deferred_safety():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    row = _session_row(session_id)
    assert row.flow_contract_version == "v3-owner-flow-1"
    assert row.safety_policy == "deferred_v3"
    assert row.input_revision == 1
    assert row.input_mode is None


def test_unknown_flow_contract_version_is_rejected():
    headers = _guest_headers()
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"unknown-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3.0"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLOW_CONTRACT_UNSUPPORTED"


def test_legacy_session_has_no_flow_contract():
    headers = _guest_headers()
    session_id = _legacy_session(headers)
    row = _session_row(session_id)
    assert row.flow_contract_version is None
    assert row.input_revision is None
    assert row.safety_policy is None


def test_select_mode_then_replace_and_discard_document():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)

    select = _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    assert select.status_code == 201, select.text
    assert _v3_data(select)["input_mode"] == "with_document"
    assert _v3_data(select)["input_revision"] == 2

    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="近期睡眠不足。"
        )

    replace = _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    assert replace.status_code == 201, replace.text
    data = _v3_data(replace)
    assert data["input_mode"] == "with_document"
    assert data["input_revision"] == 3
    assert data["active_document_id"] == document_id

    discard = _transition(
        headers, session_id, "disc-1",
        {"expected_input_revision": 3, "action": "discard_document"},
    )
    assert discard.status_code == 201, discard.text
    data = _v3_data(discard)
    assert data["input_mode"] == "without_document"
    assert data["input_revision"] == 4
    assert data["active_document_id"] is None
    assert data["understanding_ref"] is None


def test_replace_document_rejects_ocr_failed_document():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id,
            ocr_text=None, ocr_error_code="OCR_FAILED",
        )
    response = _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DOCUMENT_OCR_NOT_READY"


def test_transition_requires_matching_input_revision():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    response = _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 99, "action": "select_mode", "input_mode": "with_document"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_transition_on_legacy_session_is_rejected():
    headers = _guest_headers()
    session_id = _legacy_session(headers)
    response = _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLOW_CONTRACT_MISMATCH"


def test_transition_is_idempotent_and_cross_user_isolated():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    first = _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    assert first.status_code == 201
    replay = _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    assert replay.status_code == 200
    assert _v3_data(replay)["input_revision"] == _v3_data(first)["input_revision"]

    stranger = _guest_headers()
    denied = _transition(
        stranger, session_id, "sel-2",
        {"expected_input_revision": 2, "action": "select_mode", "input_mode": "with_document"},
    )
    assert denied.status_code == 404


def test_edited_summary_text_confirms_new_revision():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="材料提到睡眠恢复不足。"
        )
    _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    input_revision = _bind_document_set(headers, session_id, document_id, 3)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-1"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )["understanding_id"]

    # Full-text edit requires fact re-extraction, which is unavailable without
    # a configured Understanding provider — it must fail with a stable error
    # and leave the old revision intact (never publish empty facts as confirmed).
    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "confirm-1"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": input_revision,
            "decision": "confirm_with_changes",
            "edited_summary_text": "资料提到近期入睡较慢，白天有些疲惫。",
            "reprocess_requested": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FACT_EXTRACTION_UNAVAILABLE"

    read = _v3_data(
        client.get(f"/api/v3/understandings/{understanding_id}", headers=headers)
    )
    assert read["revision"] == 1
    assert read["status"] == "needs_confirmation"
    assert read["case_summary"]["summary"].startswith("材料提到睡眠恢复不足")
    assert read["safety_status"] is None

    # The failed edit must leave every piece of state untouched: no new
    # revision, no input_revision bump, no active-understanding bind, no facts,
    # no half-written database rows.
    row = _session_row(session_id)
    assert row.input_revision == 4
    assert row.active_understanding_id is None
    assert row.active_understanding_revision is None
    with _seed_db() as session:
        assert (
            session.query(UnderstandingRevision)
            .filter(UnderstandingRevision.understanding_id == understanding_id)
            .count()
            == 1
        )
        assert session.query(SessionInputRevision).count() == 4
        assert session.query(NormalizedFact).count() == 0


def test_reprocess_without_edited_text_is_rejected():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="内容。"
        )
    _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 1, "action": "replace_document", "document_id": document_id},
    )
    input_revision = _bind_document_set(headers, session_id, document_id, 2)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-1"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )["understanding_id"]
    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "confirm-1"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": input_revision,
            "decision": "confirm",
            "reprocess_requested": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REPROCESS_NOT_SUPPORTED"


def test_confirm_with_wrong_input_revision_conflicts():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="内容。"
        )
    _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    input_revision = _bind_document_set(headers, session_id, document_id, 3)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-1"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )["understanding_id"]
    response = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "confirm-1"},
        json={
            "schema_version": "understanding_v3.1",
            "expected_revision": 1,
            "expected_input_revision": 999,
            "decision": "confirm",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INPUT_REVISION_CONFLICT"


def test_v31_excludes_user_goal_but_v30_keeps_required_user_goal():
    from backend.app.schemas.v3.assessment import (
        AssessmentV31Request,
        AssessmentV31Response,
        AssessmentV3Request,
    )
    from backend.app.schemas.v3.prescription import PrescriptionV31Request, PrescriptionV3Request

    v31 = AssessmentV31Request.model_validate(
        {
            "schema_version": "assessment_v3.1",
            "session_id": "sess_1",
            "expected_input_revision": 3,
            "understanding_ref": None,
            "questionnaire_ref": None,
        }
    )
    assert v31.schema_version == "assessment_v3.1"

    with pytest.raises(pydantic.ValidationError):
        AssessmentV31Request.model_validate(
            {
                "schema_version": "assessment_v3.1",
                "session_id": "sess_1",
                "expected_input_revision": 3,
                "understanding_ref": None,
                "questionnaire_ref": None,
                "user_goal": {
                    "primary_goal": "sleep",
                    "secondary_goal": None,
                    "custom_goal_text": None,
                },
            }
        )
    assert "user_goal" not in AssessmentV31Request.model_fields
    assert "user_goal" not in AssessmentV31Response.model_fields

    # v3.0 request still requires user_goal (backward compatible).
    with pytest.raises(pydantic.ValidationError):
        AssessmentV3Request.model_validate(
            {
                "schema_version": "assessment_v3.0",
                "session_id": "sess_1",
                "understanding_ref": {"understanding_id": "u", "revision": 1},
                "questionnaire_ref": None,
            }
        )

    p31 = PrescriptionV31Request.model_validate(
        {"schema_version": "prescription_v3.1", "diagnosis_id": "d1", "preference_snapshot": None}
    )
    assert p31.schema_version == "prescription_v3.1"
    with pytest.raises(pydantic.ValidationError):
        PrescriptionV31Request.model_validate(
            {
                "schema_version": "prescription_v3.1",
                "diagnosis_id": "d1",
                "preference_snapshot": None,
                "user_goal": {"primary_goal": "sleep", "secondary_goal": None, "custom_goal_text": None},
            }
        )
    with pytest.raises(pydantic.ValidationError):
        PrescriptionV3Request.model_validate(
            {"schema_version": "prescription_v3.0", "diagnosis_id": "d1", "preference_snapshot": None}
        )


def test_without_document_requires_complete_questionnaire_for_assessment():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    with _seed_db() as session:
        row = session.query(SessionModel).filter(SessionModel.session_id == session_id).one()
        with pytest.raises(AssessmentInputNotReady) as exc:
            validate_assessment_input_readiness(session, row)
        assert exc.value.code == "QUESTIONNAIRE_REQUIRED"

        # Partial draft (5 answers) is still rejected.
        user_pk = _user_pk(session, headers["Authorization"])
        partial = QuestionnaireSubmissionV3(
            questionnaire_submission_id=f"qsub_{uuid.uuid4().hex}",
            internal_user_pk=user_pk,
            session_row_id=row.id,
            schema_id="questionnaire_v3",
            schema_version="3.0.0",
            manifest_version="medical_v3.0",
            content_checksum="sha256:partial",
            time_window_days=7,
            answers_json=[{"question_id": f"q{i:02d}"} for i in range(1, 6)],
            idempotency_key=f"idem-{uuid.uuid4().hex}",
            submitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        session.add(partial)
        session.flush()
        row.active_questionnaire_submission_id = partial.questionnaire_submission_id
        with pytest.raises(AssessmentInputNotReady) as exc2:
            validate_assessment_input_readiness(session, row)
        assert exc2.value.code == "QUESTIONNAIRE_INCOMPLETE"

        # A complete 10-answer submission with the canonical manifest values
        # satisfies the gate.
        complete = _make_submission(
            session,
            user_pk=user_pk,
            session_row_id=row.id,
            answers_json=[{"question_id": f"q{i:02d}"} for i in range(1, 11)],
        )
        row.active_questionnaire_submission_id = complete.questionnaire_submission_id
        validate_assessment_input_readiness(session, row)


def _approved_manifest() -> dict:
    """The canonical approved questionnaire manifest (PR #89) — single source
    of truth for schema_id / schema_version / manifest_version / checksum."""
    from pathlib import Path

    return json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "knowledge" / "v3" / "questionnaire-v3.0.json"
        ).read_text(encoding="utf-8")
    )


def _make_submission(session, *, user_pk, session_row_id, answers_json, content_checksum=None):
    manifest = _approved_manifest()
    submission = QuestionnaireSubmissionV3(
        questionnaire_submission_id=f"qsub_{uuid.uuid4().hex}",
        internal_user_pk=user_pk,
        session_row_id=session_row_id,
        schema_id=manifest["schema_id"],
        schema_version=manifest["schema_version"],
        manifest_version=manifest["manifest_version"],
        content_checksum=(
            manifest["content_checksum"] if content_checksum is None else content_checksum
        ),
        time_window_days=7,
        answers_json=answers_json,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        submitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    session.add(submission)
    session.flush()
    return submission


def test_readiness_rejects_duplicate_missing_unknown_and_old_v2_questions():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    canonical = [f"q{i:02d}" for i in range(1, 11)]

    with _seed_db() as session:
        row = session.query(SessionModel).filter(SessionModel.session_id == session_id).one()
        user_pk = _user_pk(session, headers["Authorization"])

        def assert_rejected(answers_json):
            submission = _make_submission(
                session, user_pk=user_pk, session_row_id=row.id, answers_json=answers_json
            )
            row.active_questionnaire_submission_id = submission.questionnaire_submission_id
            with pytest.raises(AssessmentInputNotReady) as exc:
                validate_assessment_input_readiness(session, row)
            assert exc.value.code == "QUESTIONNAIRE_INCOMPLETE"

        # Duplicate question: 10 answers but q01 twice, q10 missing.
        dup = [{"question_id": canonical[0]}] * 2 + [
            {"question_id": qid} for qid in canonical[1:9]
        ]
        assert len(dup) == 10
        assert_rejected(dup)

        # Missing question: only 9 distinct answers.
        assert_rejected([{"question_id": qid} for qid in canonical[:9]])

        # Unknown question: replace q10 with q99.
        assert_rejected(
            [{"question_id": qid} for qid in canonical[:9]] + [{"question_id": "q99"}]
        )

        # Old V2 question ids must not be accepted.
        assert_rejected(
            [{"question_id": qid} for qid in canonical[:9]] + [{"question_id": "q01_user_goal"}]
        )

        # Cross-user submission is rejected even if the answers are valid.
        stranger = _make_submission(
            session,
            user_pk=user_pk + 999,
            session_row_id=row.id,
            answers_json=[{"question_id": qid} for qid in canonical],
        )
        row.active_questionnaire_submission_id = stranger.questionnaire_submission_id
        with pytest.raises(AssessmentInputNotReady) as exc:
            validate_assessment_input_readiness(session, row)
        assert exc.value.code == "QUESTIONNAIRE_NOT_OWNED"


def test_readiness_rejects_wrong_checksum_and_schema_identity():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    canonical = [{"question_id": f"q{i:02d}"} for i in range(1, 11)]

    with _seed_db() as session:
        row = session.query(SessionModel).filter(SessionModel.session_id == session_id).one()
        user_pk = _user_pk(session, headers["Authorization"])

        # Wrong checksum (correct sha256 prefix, wrong value) must be rejected.
        bad_checksum = _make_submission(
            session, user_pk=user_pk, session_row_id=row.id, answers_json=canonical,
            content_checksum="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        )
        row.active_questionnaire_submission_id = bad_checksum.questionnaire_submission_id
        with pytest.raises(AssessmentInputNotReady) as exc:
            validate_assessment_input_readiness(session, row)
        assert exc.value.code == "QUESTIONNAIRE_INVALID_CHECKSUM"

        # A valid submission with the canonical manifest values passes.
        good = _make_submission(
            session, user_pk=user_pk, session_row_id=row.id, answers_json=canonical
        )
        row.active_questionnaire_submission_id = good.questionnaire_submission_id
        validate_assessment_input_readiness(session, row)


def test_confirmation_returns_read_model_and_input_revision():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="材料提到睡眠恢复不足。"
        )
    _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    input_revision = _bind_document_set(headers, session_id, document_id, 3)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-1"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )["understanding_id"]

    result = _v3_data(
        client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": "confirm-1"},
            json={
                "schema_version": "understanding_v3.1",
                "expected_revision": 1,
                "expected_input_revision": input_revision,
                "decision": "confirm",
            },
        )
    )
    assert result["revision"] == 2
    assert result["status"] == "confirmed"
    assert result["input_revision"] == 5
    assert result["understanding"]["understanding_id"] == understanding_id
    assert result["understanding"]["revision"] == 2
    assert result["understanding"]["status"] == "confirmed"


def test_confirmation_replay_returns_first_success_state():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="材料内容。"
        )
    _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    input_revision = _bind_document_set(headers, session_id, document_id, 3)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-1"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )["understanding_id"]

    confirm_body = {
        "schema_version": "understanding_v3.1",
        "expected_revision": 1,
        "expected_input_revision": input_revision,
        "decision": "confirm",
    }
    first = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "confirm-1"},
        json=confirm_body,
    )
    assert first.status_code == 201
    assert _v3_data(first)["input_revision"] == 5

    # A later transition advances the session input_revision.
    _transition(
        headers, session_id, "disc-1",
        {"expected_input_revision": 5, "action": "discard_document"},
    )

    replay = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "confirm-1"},
        json=confirm_body,
    )
    assert replay.status_code == 200
    data = _v3_data(replay)
    assert data["revision"] == 2
    assert data["input_revision"] == 5  # first success's, not the later 6
    assert data["understanding"]["revision"] == 2
    assert data["understanding"]["status"] == "confirmed"

    # Replay must not create any new revision, input_revision bump, or snapshot.
    row = _session_row(session_id)
    assert row.input_revision == 6  # unchanged from discard, not bumped to 7
    with _seed_db() as session:
        assert (
            session.query(UnderstandingRevision)
            .filter(UnderstandingRevision.understanding_id == understanding_id)
            .count()
            == 2
        )
        assert session.query(SessionInputRevision).count() == 6

    # Same Idempotency-Key with a different payload is an idempotency conflict.
    conflict = client.post(
        f"/api/v3/understandings/{understanding_id}/confirmations",
        headers={**headers, "Idempotency-Key": "confirm-1"},
        json={**confirm_body, "expected_input_revision": 6},
    )
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_v31_rejects_legacy_reject_and_cannot_confirm():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id, ocr_text="材料内容。"
        )
    _transition(
        headers, session_id, "rep-1",
        {"expected_input_revision": 2, "action": "replace_document", "document_id": document_id},
    )
    input_revision = _bind_document_set(headers, session_id, document_id, 3)
    understanding_id = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-1"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )["understanding_id"]

    for decision in ("reject_source", "cannot_confirm"):
        response = client.post(
            f"/api/v3/understandings/{understanding_id}/confirmations",
            headers={**headers, "Idempotency-Key": f"confirm-{decision}"},
            json={
                "schema_version": "understanding_v3.1",
                "expected_revision": 1,
                "expected_input_revision": input_revision,
                "decision": decision,
            },
        )
        assert response.status_code == 422


def test_with_document_requires_confirmed_understanding_for_assessment():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    _transition(
        headers, session_id, "sel-1",
        {"expected_input_revision": 1, "action": "select_mode", "input_mode": "with_document"},
    )
    with _seed_db() as session:
        row = session.query(SessionModel).filter(SessionModel.session_id == session_id).one()
        with pytest.raises(AssessmentInputNotReady) as exc:
            validate_assessment_input_readiness(session, row)
        assert exc.value.code == "UNDERSTANDING_NOT_CONFIRMED"


def test_ocr_failure_never_confirms_in_new_flow():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    with _seed_db() as session:
        user_pk = _user_pk(session, headers["Authorization"])
        document_id = _seed_document(
            session, user_pk=user_pk, session_id=session_id,
            ocr_text=None, ocr_error_code="OCR_FAILED",
        )
        session_row = session.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).one()
        session_row.input_mode = "with_document"
        session_row.active_document_id = document_id
        session_row.input_revision = 2
        session.commit()
    input_revision = _bind_document_set(
        headers, session_id, document_id, 2, outcome="INVALID"
    )
    data = _v3_data(
        client.post(
            "/api/v3/understandings",
            headers={**headers, "Idempotency-Key": "und-fail"},
            json={
                "schema_version": "understanding_v3.1",
                "session_id": session_id,
                "expected_input_revision": input_revision,
                "inputs": [
                    {
                        "source_id": "src_1",
                        "source_type": "document",
                        "processing_status": "ready",
                        "text_ref": document_id,
                        "captured_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
    )
    assert data["status"] == "failed"
    assert data["case_summary"] is None
    assert data["source_statuses"][0]["status"] == "skipped"
    assert data["safety_status"] is None

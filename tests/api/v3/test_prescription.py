"""Agent 3 (Prescription) persistence tests (Issue #99 step 5)."""

import base64
from contextlib import contextmanager
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import AssessmentRevisionV3, AssessmentV3
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.models.v3.identity import UserIdentity
from backend.app.models.v3.understanding import (
    UnderstandingRevision,
    UnderstandingRun,
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


def _new_flow_session(headers) -> str:
    response = client.post(
        "/api/v3/sessions",
        headers={**headers, "Idempotency-Key": f"seed-{uuid.uuid4().hex}"},
        json={"flow_contract_version": "v3-owner-flow-1"},
    )
    assert response.status_code == 201, response.text
    return _v3_data(response)["session_id"]


def _seed_diagnosis(headers, session_id):
    with _seed_db() as session:
        user = (
            session.query(UserIdentity)
            .filter(
                UserIdentity.public_user_id
                == _public_user_id(headers["Authorization"].split()[1])
            )
            .one()
        )
        sess = (
            session.query(SessionModel)
            .filter(SessionModel.session_id == session_id)
            .one()
        )
        understanding_id = f"und_{uuid.uuid4().hex}"
        session.add(
            UnderstandingRun(
                understanding_id=understanding_id,
                internal_user_pk=user.internal_user_pk,
                session_row_id=sess.id,
                current_revision=1,
                status="confirmed",
                safety_status=None,
                degradation_json={},
            )
        )
        session.add(
            UnderstandingRevision(
                understanding_id=understanding_id,
                revision=1,
                status="confirmed",
                presentation_json={},
                confirmation_decision="confirm",
            )
        )
        assessment_id = f"asmt_{uuid.uuid4().hex}"
        session.add(
            AssessmentV3(
                assessment_id=assessment_id,
                internal_user_pk=user.internal_user_pk,
                session_row_id=sess.id,
                understanding_id=understanding_id,
                understanding_revision=1,
                current_revision=1,
                status="confirmed",
                safety_status=None,
                user_goal_json=None,
            )
        )
        session.add(
            AssessmentRevisionV3(
                assessment_id=assessment_id,
                revision=1,
                understanding_revision=1,
                status="confirmed",
                confirmation_status="confirmed",
                state_summary="state",
                organ_profile_json={},
                evidence_coverage=0.8,
                source_diversity=1,
                conflicts_json=[],
                missing_information_json=[],
                degradation_json={},
                presentation_json={},
            )
        )
        diagnosis_id = f"diag_{uuid.uuid4().hex}"
        session.add(
            DiagnosisRun(
                diagnosis_id=diagnosis_id,
                internal_user_pk=user.internal_user_pk,
                session_row_id=sess.id,
                assessment_id=assessment_id,
                assessment_revision=1,
                status="success",
                abstained=0,
                degradation_json={},
                presentation_json={},
            )
        )
        session.commit()
        return diagnosis_id


def test_create_and_read_prescription():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    created = client.post(
        "/api/v3/prescriptions",
        headers=headers,
        json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
    )
    assert created.status_code == 201, created.text
    data = _v3_data(created)
    assert data["status"] == "success"
    assert data["prescription_mode"] == "syndrome_based"
    assert data["generation_spec"]["tone_profile"]["dominant_tone"] == "gong"

    read = _v3_data(
        client.get(f"/api/v3/prescriptions/{data['prescription_id']}", headers=headers)
    )
    assert read["prescription_id"] == data["prescription_id"]


def test_prescription_requires_owned_diagnosis():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    stranger = _guest_headers()
    response = client.post(
        "/api/v3/prescriptions",
        headers=stranger,
        json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
    )
    assert response.status_code == 404


def test_prescription_cross_user_read_is_isolated():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)
    prescription_id = _v3_data(
        client.post(
            "/api/v3/prescriptions",
            headers=headers,
            json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
        )
    )["prescription_id"]

    stranger = _guest_headers()
    denied = client.get(f"/api/v3/prescriptions/{prescription_id}", headers=stranger)
    assert denied.status_code == 404

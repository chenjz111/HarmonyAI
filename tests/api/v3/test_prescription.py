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
from backend.app.models.v3.prescription import PrescriptionV3
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


def _seed_diagnosis(
    headers, session_id, *, status="success", abstained=0, abstain_reason=None
):
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
                status=status,
                abstained=abstained,
                abstain_reason=abstain_reason,
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
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
    )
    assert created.status_code == 201, created.text
    data = _v3_data(created)
    assert data["status"] == "degraded"
    assert data["prescription_mode"] == "wellness"
    assert data["generation_spec"]["tone_profile"]["primary_tone"] == "gong"
    assert data["generation_spec"]["tone_profile"]["secondary_tone"] is None

    read = _v3_data(
        client.get(f"/api/v3/prescriptions/{data['prescription_id']}", headers=headers)
    )
    assert read["prescription_id"] == data["prescription_id"]


def _submit_questionnaire(headers, session_id):
    from pathlib import Path

    manifest = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "knowledge" / "v3" / "questionnaire-v3.0.1.json"
        ).read_text(encoding="utf-8")
    )
    client.post(
        f"/api/v3/sessions/{session_id}/input-transitions",
        headers={**headers, "Idempotency-Key": f"sel-{uuid.uuid4().hex}"},
        json={"expected_input_revision": 1, "action": "select_mode", "input_mode": "without_document"},
    )
    response = client.post(
        f"/api/v3/sessions/{session_id}/questionnaire",
        headers={**headers, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
        json={
            "session_id": session_id,
            "expected_input_revision": 2,
            "schema_id": manifest["schema_id"],
            "schema_version": manifest["schema_version"],
            "manifest_version": manifest["manifest_version"],
            "content_checksum": manifest["content_checksum"],
            "answers": (
                [
                    {"question_id": f"q{i:02d}", "answer_type": "frequency_0_4", "value": 0}
                    for i in range(1, 6)
                ]
                + [
                    {"question_id": f"q{i:02d}", "answer_type": "multi_choice_evidence", "value": ["none"]}
                    for i in range(6, 11)
                ]
            ),
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:05:00Z",
        },
    )
    assert response.status_code == 201, response.text


def test_user_goal_influences_prescription_bpm():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)
    _submit_questionnaire(headers, session_id)

    submitted = client.put(
        f"/api/v3/sessions/{session_id}/user-goal",
        headers=headers,
        json={"user_goal": {"primary_goal": "energy", "secondary_goal": None, "custom_goal_text": None}},
    )
    assert submitted.status_code == 200, submitted.text

    created = _v3_data(
        client.post(
            "/api/v3/prescriptions",
            headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
            json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
        )
    )
    assert created["generation_spec"]["bpm"] == 82
    assert created["generation_spec"]["energy_curve"] == "轻快有活力"


def test_prescription_requires_owned_diagnosis():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    stranger = _guest_headers()
    response = client.post(
        "/api/v3/prescriptions",
        headers={**stranger, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
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
            headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
            json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
        )
    )["prescription_id"]

    stranger = _guest_headers()
    denied = client.get(f"/api/v3/prescriptions/{prescription_id}", headers=stranger)
    assert denied.status_code == 404


def _generation_spec(diagnosis_id, *, revision=1, primary_tone="zhi", instruments=("pipa", "xiao")):
    weights = {"jiao": 0.1, "zhi": 0.1, "gong": 0.1, "shang": 0.1, "yu": 0.1}
    weights[primary_tone] = 0.6
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": {
            "schema_version": "tone_profile_v3.1",
            "weights": weights,
            "primary_tone": primary_tone,
            "secondary_tone": None,
            "score_semantics": "relative_tone_distribution",
            "mapping_version": "tone_mapping_v3.0",
            "basis": {
                "diagnosis_id": diagnosis_id,
                "diagnosis_revision": revision,
                "supporting_evidence_refs": [],
            },
        },
        "bpm": 66,
        "duration_seconds": 180,
        "instruments": list(instruments),
        "ambient_sounds": [],
        "structure": {"intro_seconds": 30, "main_seconds": 120, "outro_seconds": 30},
        "energy_curve": "平稳舒缓",
        "forbidden_constraints": [],
        "fallback_policy": {"allow_local_matching": True},
    }


def test_real_generation_spec_is_accepted_and_bound():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    created = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "generation_spec": _generation_spec(diagnosis_id),
            "preference_snapshot": None,
        },
    )
    assert created.status_code == 201, created.text
    data = _v3_data(created)
    assert data["status"] == "success"
    assert data["prescription_mode"] == "syndrome_based"
    assert data["generation_spec"]["tone_profile"]["primary_tone"] == "zhi"
    # Presentation derives from the real spec, not a hardcoded 宫调/古琴.
    assert data["presentation"]["tone_summary"] == "徵调为主，平稳舒缓。"
    assert "pipa、xiao" in data["presentation"]["parameter_summaries"][0]


def test_generation_spec_with_mismatched_diagnosis_id_is_rejected():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    spec = _generation_spec(diagnosis_id)
    spec["tone_profile"]["basis"]["diagnosis_id"] = "diag_someone_else"
    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "generation_spec": spec,
            "preference_snapshot": None,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPEC_DIAGNOSIS_MISMATCH"


def test_generation_spec_with_mismatched_revision_is_rejected():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "generation_spec": _generation_spec(diagnosis_id, revision=99),
            "preference_snapshot": None,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPEC_REVISION_MISMATCH"


def test_abstained_diagnosis_falls_back_to_wellness():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(
        headers, session_id, status="abstained", abstained=1, abstain_reason="safe_user"
    )

    created = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
    )
    assert created.status_code == 201, created.text
    data = _v3_data(created)
    assert data["status"] == "degraded"
    assert data["prescription_mode"] == "wellness"
    assert data["generation_spec"]["tone_profile"]["primary_tone"] == "gong"


def test_abstained_diagnosis_rejects_generation_spec():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(
        headers, session_id, status="abstained", abstained=1, abstain_reason="safe_user"
    )

    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "generation_spec": _generation_spec(diagnosis_id),
            "preference_snapshot": None,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SPEC_UNEXPECTED_FOR_ABSTAINED"


def test_withheld_diagnosis_is_not_ready():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id, status="withheld")

    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DIAGNOSIS_NOT_READY"


def test_prescription_idempotent_replay():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    key = f"rx-idem-{uuid.uuid4().hex}"
    payload = {"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None}
    first = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": key},
        json=payload,
    )
    assert first.status_code == 201, first.text
    first_id = _v3_data(first)["prescription_id"]

    second = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": key},
        json=payload,
    )
    assert second.status_code == 200, second.text
    assert _v3_data(second)["prescription_id"] == first_id


def test_user_goal_snapshot_is_persisted():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)
    _submit_questionnaire(headers, session_id)

    goal = {"primary_goal": "focus", "secondary_goal": None, "custom_goal_text": None}
    submitted = client.put(
        f"/api/v3/sessions/{session_id}/user-goal",
        headers=headers,
        json={"user_goal": goal},
    )
    assert submitted.status_code == 200, submitted.text

    prescription_id = _v3_data(
        client.post(
            "/api/v3/prescriptions",
            headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
            json={"schema_version": "prescription_v3.1", "diagnosis_id": diagnosis_id, "preference_snapshot": None},
        )
    )["prescription_id"]

    with _seed_db() as session:
        row = (
            session.query(PrescriptionV3)
            .filter(PrescriptionV3.prescription_id == prescription_id)
            .one()
        )
        assert row.user_goal_json == goal
        assert row.user_goal_revision == 1

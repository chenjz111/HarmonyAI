"""Agent 3 (Prescription) persistence tests (Issue #99 step 5)."""

import base64
from contextlib import contextmanager
from hashlib import sha256
import json
import uuid

import pytest
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
from backend.app.schemas.v3.flow_v31 import UserGoalV31


client = TestClient(app)


@pytest.fixture(autouse=True)
def _approved_agent3_assets(monkeypatch):
    from backend.app.services.v3 import internal_agent3_service

    mapping = {
        "schema_id": "five-tone_mapping_v3",
        "schema_version": "3.0.0",
        "organ_tone_weights": {
            "primary": {
                "liver": {"jiao": 0.7, "shang": 0.15, "zhi": 0.15},
                "heart": {"zhi": 0.7, "gong": 0.15, "yu": 0.15},
                "spleen": {"gong": 0.7, "zhi": 0.15, "shang": 0.15},
                "lung": {"shang": 0.7, "gong": 0.15, "jiao": 0.15},
                "kidney": {"yu": 0.7, "gong": 0.15, "shang": 0.15},
            }
        },
    }
    rules = {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "test-approved-v1",
        "asset_version": "owner-approved-test-v1",
        "review_status": "approved",
        "secondary_goal_merge_policy": "primary_over_secondary_fill_missing",
        "default": {
            "bpm": 60,
            "instruments": ["guqin"],
            "ambience": ["rain"],
            "duration_seconds": 180,
            "explanations": {
                "bpm": "approved bpm",
                "instruments": "approved instruments",
                "ambience": "approved ambience",
                "duration": "approved duration",
            },
        },
        "goals": {
            "sleep": {},
            "relaxation": {},
            "emotion_regulation": {},
            "energy": {
                "bpm": 82,
                "instruments": ["pipa", "xiao"],
                "ambience": ["stream"],
                "duration_seconds": 180,
            },
            "focus": {
                "bpm": 76,
                "instruments": ["guqin"],
                "ambience": ["rain"],
                "duration_seconds": 180,
            },
            "stress_relief": {},
            "other": {},
        },
    }
    monkeypatch.setattr(
        internal_agent3_service,
        "load_agent3_assets",
        lambda: (mapping, rules),
    )


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
                flow_contract_version="v3-owner-flow-1",
                input_revision=sess.input_revision,
            )
        )
        session.add(
            AssessmentRevisionV3(
                assessment_id=assessment_id,
                revision=1,
                understanding_revision=1,
                input_revision=sess.input_revision,
                status="confirmed",
                confirmation_status="confirmed",
                state_summary="state",
                organ_profile_json={
                    "status": "available",
                    "weights": {
                        "liver": 0.7,
                        "heart": 0.1,
                        "spleen": 0.1,
                        "lung": 0.05,
                        "kidney": 0.05,
                    },
                },
                evidence_coverage=0.8,
                source_diversity=1,
                conflicts_json=[],
                missing_information_json=[],
                degradation_json={},
                presentation_json={},
            )
        )
        diagnosis_id = f"diag_{uuid.uuid4().hex}"
        diagnosis = DiagnosisRun(
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
        session.add(diagnosis)
        sess.active_understanding_id = understanding_id
        sess.active_understanding_revision = 1
        session.flush()
        if not abstained and status not in {"withheld", "failed"}:
            from backend.app.services.v3.internal_agent3_service import (
                build_prescription_spec,
            )

            user_goal = (
                UserGoalV31.model_validate(sess.user_goal_json)
                if sess.user_goal_json is not None
                else None
            )
            spec = build_prescription_spec(session, diagnosis, user_goal)
            read_model = {
                "schema_version": "five_tone_analysis_read_model_v3.1",
                "confirmed_user_state_ref": {
                    "confirmed_user_state_id": f"cus_{assessment_id}_1",
                    "revision": 1,
                    "content_checksum": f"sha256:{'a' * 64}",
                },
                "confirmed_state": "state",
                "state_tendency": "state tendency",
                "analysis_rationales": [{
                    "summary": "based on confirmed assessment",
                    "evidence_refs": [f"assessment:{assessment_id}:r1"],
                }],
                "primary_tone": {
                    "tone": spec.tone_profile.primary_tone.value,
                    "display_name": "角调",
                    "explanation": "primary tone",
                },
                "secondary_tone": None,
                "bpm": {"value": spec.bpm, "explanation": "approved bpm"},
                "instruments": {
                    "values": spec.instruments,
                    "explanation": "approved instruments",
                },
                "ambience": {
                    "values": spec.ambient_sounds or ["none"],
                    "explanation": "approved ambience",
                },
                "duration": {
                    "seconds": spec.duration_seconds,
                    "explanation": "approved duration",
                },
                "generation": {"status": "ready", "message": "ready"},
                "disclaimer": "本结果不构成医学诊断或治疗建议。",
            }
            canonical = json.dumps(
                read_model,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            diagnosis.five_tone_read_model_schema_version = (
                "five_tone_analysis_read_model_v3.1"
            )
            diagnosis.five_tone_read_model_json = read_model
            diagnosis.five_tone_read_model_checksum = (
                f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"
            )
            diagnosis.generation_spec_json = spec.model_dump(mode="json")
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
    assert data["status"] == "success"
    assert data["prescription_mode"] == "syndrome_based"
    assert data["generation_spec"]["tone_profile"]["primary_tone"] == "jiao"
    assert data["generation_spec"]["tone_profile"]["secondary_tone"] is None

    read = _v3_data(
        client.get(f"/api/v3/prescriptions/{data['prescription_id']}", headers=headers)
    )
    assert read["prescription_id"] == data["prescription_id"]


def test_prescription_reports_only_persisted_real_preference_changes(monkeypatch):
    from backend.app.schemas.v3.prescription import PreferenceSnapshot
    from backend.app.services.v3 import prescription_service

    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)
    preference = PreferenceSnapshot.model_validate(
        {
            "profile_id": "pref_truthful",
            "version": 4,
            "preferred_instruments": [],
            "disliked_instruments": [],
            "preferred_bpm_range": {"min": 68, "max": 68, "weight": 1.0},
            "preferred_duration_seconds": None,
            "preferred_ambient": [],
        }
    )
    monkeypatch.setattr(
        prescription_service,
        "_resolve_preference",
        lambda *args, **kwargs: preference,
    )
    with _seed_db() as session:
        diagnosis = session.query(DiagnosisRun).filter(
            DiagnosisRun.diagnosis_id == diagnosis_id
        ).one()
        generation_spec = dict(diagnosis.generation_spec_json)
        generation_spec["bpm"] = 68
        diagnosis.generation_spec_json = generation_spec
        diagnosis.preference_profile_id = preference.profile_id
        diagnosis.preference_version = preference.version
        diagnosis.preference_application_json = [
            {
                "field": "bpm",
                "before": 66,
                "after": 68,
                "applied": True,
                "reason_code": "preference_applied",
            }
        ]
        session.commit()

    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-pref-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "preference_snapshot": preference.model_dump(mode="json"),
        },
    )

    assert response.status_code == 201, response.text
    data = _v3_data(response)
    assert data["generation_spec"]["bpm"] == 68
    assert data["personalization"]["applied"] is True
    assert data["personalization"]["adjustments"] == [
        {
            "field": "bpm",
            "from": "66",
            "to": "68",
            "reason_code": "preference_applied",
        }
    ]
    assert data["presentation"]["personalization_summary"] == "已根据个人偏好微调"


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
    _submit_questionnaire(headers, session_id)

    submitted = client.put(
        f"/api/v3/sessions/{session_id}/user-goal",
        headers=headers,
        json={"user_goal": {"primary_goal": "energy", "secondary_goal": None, "custom_goal_text": None}},
    )
    assert submitted.status_code == 200, submitted.text
    diagnosis_id = _seed_diagnosis(headers, session_id)

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


def test_generation_spec_is_built_internally_from_diagnosis():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    created = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "preference_snapshot": None,
        },
    )
    assert created.status_code == 201, created.text
    data = _v3_data(created)
    assert data["status"] == "success"
    assert data["prescription_mode"] == "syndrome_based"
    assert data["generation_spec"]["tone_profile"]["primary_tone"] == "jiao"
    assert data["generation_spec"]["tone_profile"]["basis"]["diagnosis_id"] == diagnosis_id
    assert data["presentation"]["tone_summary"].startswith("角调为主")


def test_prescription_rejects_diagnosis_after_assessment_is_superseded():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    with _seed_db() as session:
        diagnosis = session.query(DiagnosisRun).filter(
            DiagnosisRun.diagnosis_id == diagnosis_id
        ).one()
        assessment = session.query(AssessmentV3).filter(
            AssessmentV3.assessment_id == diagnosis.assessment_id
        ).one()
        assessment.current_revision = 2
        session.add(
            AssessmentRevisionV3(
                assessment_id=assessment.assessment_id,
                revision=2,
                previous_revision=1,
                understanding_revision=1,
                status="confirmed",
                confirmation_status="confirmed",
                state_summary="new state",
                organ_profile_json={
                    "status": "available",
                    "weights": {
                        "liver": 0.1,
                        "heart": 0.7,
                        "spleen": 0.1,
                        "lung": 0.05,
                        "kidney": 0.05,
                    },
                },
                evidence_coverage=0.8,
                source_diversity=1,
                conflicts_json=[],
                missing_information_json=[],
                degradation_json={},
                presentation_json={},
            )
        )
        session.commit()

    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-stale-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "preference_snapshot": None,
        },
    )

    assert response.status_code == 409, response.text


def test_prescription_does_not_rerun_agent3(monkeypatch):
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

    def fail_if_rerun(*args, **kwargs):
        raise AssertionError("Agent3 must not rerun during Prescription")

    monkeypatch.setattr(
        "backend.app.services.v3.internal_agent3_service.build_prescription_spec",
        fail_if_rerun,
    )
    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-snapshot-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "preference_snapshot": None,
        },
    )

    assert response.status_code == 201, response.text


def test_client_cannot_submit_generation_spec():
    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)

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
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "generation_spec" and item["type"] == "extra_forbidden" for item in detail)


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


def test_abstained_diagnosis_also_rejects_client_generation_spec():
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
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "generation_spec" and item["type"] == "extra_forbidden" for item in detail)


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


def test_prescription_does_not_reload_agent3_assets(monkeypatch):
    from backend.app.services.v3 import internal_agent3_service

    headers = _guest_headers()
    session_id = _new_flow_session(headers)
    diagnosis_id = _seed_diagnosis(headers, session_id)
    monkeypatch.setattr(
        internal_agent3_service,
        "load_agent3_assets",
        lambda: (_ for _ in ()).throw(
            internal_agent3_service.Agent3NotReady(
                "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED",
                "music rules unavailable",
            )
        ),
    )

    response = client.post(
        "/api/v3/prescriptions",
        headers={**headers, "Idempotency-Key": f"rx-{uuid.uuid4().hex}"},
        json={
            "schema_version": "prescription_v3.1",
            "diagnosis_id": diagnosis_id,
            "preference_snapshot": None,
        },
    )

    assert response.status_code == 201, response.text


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
    _submit_questionnaire(headers, session_id)

    goal = {"primary_goal": "focus", "secondary_goal": None, "custom_goal_text": None}
    submitted = client.put(
        f"/api/v3/sessions/{session_id}/user-goal",
        headers=headers,
        json={"user_goal": goal},
    )
    assert submitted.status_code == 200, submitted.text
    diagnosis_id = _seed_diagnosis(headers, session_id)

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

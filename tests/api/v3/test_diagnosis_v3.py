"""Agent 2 Diagnosis V3 — honest abstain / degraded RAG, no fabricated
syndromes without an approved syndrome whitelist."""

import base64
import json
import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.v3.assessment import AssessmentRevisionV3
from backend.app.models.v3.identity import UserIdentity


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
    db_session, *, user_pk, session_row, organ_profile_json, assessment_id=None
):
    if assessment_id is None:
        assessment_id = f"asmt_{uuid.uuid4().hex}"
    db_session.add(
        AssessmentRevisionV3(
            assessment_id=assessment_id,
            revision=1,
            previous_revision=None,
            understanding_revision=1,
            input_revision=1,
            status="confirmed",
            confirmation_status="confirmed",
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

"""Read-only Player basis endpoint tests."""

import json
import uuid
from hashlib import sha256

from backend.app.main import app
from backend.app.models import Session as SessionModel
from backend.app.models.v3.diagnosis import DiagnosisRun
from backend.app.routers.v3 import diagnosis_router
from backend.app.schemas.v3.flow_v31 import (
    BpmExplanation,
    ConfirmedUserStateRef,
    DurationExplanation,
    FiveToneAnalysisReadModel,
    GenerationReadiness,
    ListParameterExplanation,
    PublicRationale,
    PublicToneExplanation,
)
from fastapi.testclient import TestClient

from tests.api.v3.test_diagnosis_v3 import (
    _guest_headers,
    _seed_confirmed_assessment,
    _setup_flow_session,
    _user_pk,
)


client = TestClient(app)


def _read_model() -> FiveToneAnalysisReadModel:
    return FiveToneAnalysisReadModel(
        schema_version="five_tone_analysis_read_model_v3.2",
        confirmed_user_state_ref=ConfirmedUserStateRef(
            confirmed_user_state_id="cus_read_model",
            revision=1,
            content_checksum="sha256:confirmed-state",
        ),
        confirmed_state="用户确认的近期状态摘要。",
        state_tendency="近期恢复状态需要支持。",
        analysis_rationales=[
            PublicRationale(summary="基于已确认状态整理本次方案。", evidence_refs=["fact_1"])
        ],
        regulation_mode="personalized_five_tone",
        tone_weights={"jiao": 0.4, "zhi": 0.2, "gong": 0.15, "shang": 0.15, "yu": 0.1},
        primary_tone=PublicToneExplanation(
            tone="jiao", display_name="角音", explanation="主音依据来自持久化解析。"
        ),
        secondary_tone=PublicToneExplanation(
            tone="zhi", display_name="徵音", explanation="辅音依据来自持久化解析。"
        ),
        bpm=BpmExplanation(value=60, explanation="节奏依据来自持久化解析。"),
        instruments=ListParameterExplanation(
            values=["古琴"], explanation="乐器依据来自持久化解析。"
        ),
        ambience=ListParameterExplanation(
            values=["流水"], explanation="氛围依据来自持久化解析。"
        ),
        duration=DurationExplanation(seconds=180, explanation="按方案设置。"),
        generation=GenerationReadiness(status="ready", message="可以开始生成本次音乐。"),
        disclaimer="仅用于音乐调养参考。",
    )


def test_player_basis_endpoint_reads_checksum_verified_model_without_writes(
    db_session_factory, monkeypatch
):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    diagnosis_id = f"diag_read_{uuid.uuid4().hex}"
    db.add(
        DiagnosisRun(
            diagnosis_id=diagnosis_id,
            internal_user_pk=user_pk,
            session_row_id=session_row.id,
            assessment_id="asmt_read_model",
            assessment_revision=1,
            status="success",
            abstained=0,
            degradation_json={"active": False, "reason_codes": []},
            presentation_json={"title": "辨证分析"},
        )
    )
    db.commit()
    db.close()

    monkeypatch.setattr(
        diagnosis_router,
        "load_current_five_tone_read_model",
        lambda _db, _diagnosis, _session: _read_model(),
    )

    response = client.get(
        f"/api/v3/diagnoses/{diagnosis_id}/five-tone-analysis", headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["confirmed_state"] == "用户确认的近期状态摘要。"
    assert payload["primary_tone"]["explanation"] == "主音依据来自持久化解析。"
    assert payload["secondary_tone"]["explanation"] == "辅音依据来自持久化解析。"

    audit = db_session_factory()
    try:
        row = audit.query(DiagnosisRun).filter(DiagnosisRun.diagnosis_id == diagnosis_id).one()
        assert row.status == "success"
        assert row.five_tone_read_model_json is None
    finally:
        audit.close()


def test_player_basis_endpoint_hides_foreign_diagnosis(db_session_factory):
    headers = _guest_headers()
    stranger = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    diagnosis_id = f"diag_read_{uuid.uuid4().hex}"
    db.add(
        DiagnosisRun(
            diagnosis_id=diagnosis_id,
            internal_user_pk=user_pk,
            session_row_id=session_row.id,
            assessment_id="asmt_read_model",
            assessment_revision=1,
            status="success",
            abstained=0,
            degradation_json={"active": False, "reason_codes": []},
            presentation_json={"title": "辨证分析"},
        )
    )
    db.commit()
    db.close()

    response = client.get(
        f"/api/v3/diagnoses/{diagnosis_id}/five-tone-analysis", headers=stranger
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_player_basis_endpoint_returns_checksum_verified_confirmed_state(
    db_session_factory,
):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        assessment_id=f"asmt_read_{uuid.uuid4().hex}",
        organ_profile_json={
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        },
    )
    diagnosis_id = f"diag_read_{uuid.uuid4().hex}"
    payload = _read_model().model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    from backend.app.models.v3.diagnosis import DiagnosisRun

    db.add(
        DiagnosisRun(
            diagnosis_id=diagnosis_id,
            internal_user_pk=user_pk,
            session_row_id=session_row.id,
            assessment_id=assessment_id,
            assessment_revision=1,
            status="success",
            abstained=0,
            degradation_json={"active": False, "reason_codes": []},
            presentation_json={"title": "辨证分析"},
            five_tone_read_model_schema_version=payload["schema_version"],
            five_tone_read_model_json=payload,
            five_tone_read_model_checksum=f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}",
        )
    )
    db.commit()
    db.close()

    response = client.get(
        f"/api/v3/diagnoses/{diagnosis_id}/five-tone-analysis", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["confirmed_state"] == "用户确认的近期状态摘要。"

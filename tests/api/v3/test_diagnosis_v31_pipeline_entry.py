"""Formal V3.1 Router entry coverage at the approved dependency boundary.

These tests use fake transports/dependencies and are Mock integration tests;
they are deliberately not evidence of a real Embedding, Chroma, or Qwen
Smoke run.
"""

from types import SimpleNamespace
from hashlib import sha256
import json
import uuid

from backend.app.core import agent_config
from backend.app.schemas.v3.common import Degradation
from backend.app.models.v3.diagnosis import (
    AiProviderRun,
    DiagnosisRun,
    RagRetrievalHit,
    RagRetrievalRun,
)
from backend.app.schemas.v3.diagnosis import IngestionManifest, RagHit, RagResult
from backend.app.schemas.v3.prescription import PreferenceSnapshot
from backend.app.schemas.v3.flow_v31 import (
    ConfirmedUserState,
    FiveToneAnalysisReadModel,
)
from backend.app.services.v3 import diagnosis_service

from tests.api.v3.test_diagnosis_v3 import (
    _diagnosis_body,
    _guest_headers,
    _seed_confirmed_assessment,
    _setup_flow_session,
    _user_pk,
    client,
)


def _rag_result() -> RagResult:
    return RagResult(
        retrieval_id="rag_formal_entry",
        status="success",
        knowledge_version="medical_v3.1",
        embedding_version="text-embedding-v4@1024",
        retrieval_score_semantics="normalized_similarity",
        hits=[
            RagHit(
                chunk_id="chunk_1",
                source_id="source_1",
                source_title="approved source",
                section="section",
                retrieval_score=0.9,
                text="approved text",
                display_summary="approved summary",
                review_status="approved",
            )
        ],
        degradation=Degradation(active=False, reason_codes=[]),
    )


def _manifest() -> IngestionManifest:
    return IngestionManifest(
        knowledge_version="medical_v3.1",
        embedding_provider="aliyun",
        embedding_model="text-embedding-v4",
        embedding_version="text-embedding-v4@1024",
        distance_metric="cosine",
        retrieval_score_semantics="normalized_similarity",
        minimum_score=0.5,
        chunk_count=1,
        manifest_checksum="sha256:manifest-formal-test",
        review_status="approved",
    )


def _confirmed_state_for(session_id: str) -> ConfirmedUserState:
    from tests.ai_engine.v3.test_v31_pipeline import _confirmed_state

    return _confirmed_state().model_copy(update={"session_id": session_id})


def _dependencies(calls: list[str], *, rag_result: RagResult | None = None):
    from backend.app.schemas.v3.diagnosis import DiagnosisProviderResponse
    from tests.ai_engine.v3.test_v31_pipeline import _mapping, _rules

    mapping = _mapping()
    mapping["organ_tone_weights"]["primary"] = {
        organ: {"zhi": 1.0}
        for organ in ("liver", "heart", "spleen", "lung", "kidney")
    }

    class FakeRagStore:
        manifest = _manifest()
        approved_chunk_ids = frozenset({"chunk_1"})

        def query(self, query):
            calls.append(f"rag:{query.query_id}")
            return rag_result or _rag_result()

    class FakeProvider:
        allowed_syndrome_codes = {"syndrome_1"}
        allowed_fact_ids = set()
        allowed_chunk_ids = {"chunk_1"}
        medical_rule_version = "medical-rules-v3.1-r1"

        async def acomplete_json(self, *, request, facts, rag_chunk_ids):
            calls.append("qwen")
            assert request.schema_version == "diagnosis_provider_v3.0"
            assert request.response_schema_version == "diagnosis_provider_response_v3.0"
            assert not facts
            assert rag_chunk_ids == ["chunk_1"]
            return DiagnosisProviderResponse.model_validate(
                {
                    "status": "success",
                    "candidate_tendencies": [
                        {
                            "syndrome_code": "syndrome_1",
                            "display_name": "safe tendency",
                            "relative_support": 0.8,
                            "supporting_fact_ids": [],
                            "contradicting_fact_ids": [],
                            "knowledge_chunk_ids": ["chunk_1"],
                            "reasoning_summary": "grounded summary",
                        }
                    ],
                    "abstained": False,
                    "abstain_reason": None,
                }
            )

    return SimpleNamespace(
        rag_store=FakeRagStore(),
        diagnosis_provider=FakeProvider(),
        tone_mapping=mapping,
        generation_parameter_rules=_rules(),
        allowed_syndrome_codes=frozenset({"syndrome_1"}),
        medical_rule_version="medical-rules-v3.1-r1",
    )


def test_formal_router_reaches_v31_pipeline_factory_and_mock_chain(
    db_session_factory, monkeypatch
):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.0,
                "heart": 1.0,
                "spleen": 0.0,
                "lung": 0.0,
                "kidney": 0.0,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    calls: list[str] = []
    dependencies = _dependencies(calls)
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: (calls.append("factory") or dependencies),
    )
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )
    monkeypatch.setattr(
        diagnosis_service,
        "get_latest_preference_snapshot",
        lambda *args, **kwargs: PreferenceSnapshot.model_validate(
            {
                "profile_id": "pref_formal",
                "version": 3,
                "preferred_instruments": [],
                "disliked_instruments": [],
                "preferred_bpm_range": {"min": 66, "max": 66, "weight": 1.0},
                "preferred_duration_seconds": None,
                "preferred_ambient": [],
            }
        ),
    )

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"formal-{uuid.uuid4().hex}"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["status"] == "success"
    assert calls[0] == "factory"
    assert any(item.startswith("rag:") for item in calls)
    assert calls[-1] == "qwen"

    audit_db = db_session_factory()
    try:
        diagnosis = audit_db.query(DiagnosisRun).one()
        assert diagnosis.rag_run_id == "rag_formal_entry"
        assert diagnosis.provider_run_id
        restored = FiveToneAnalysisReadModel.model_validate(
            diagnosis.five_tone_read_model_json
        )
        canonical = json.dumps(
            restored.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        assert (
            diagnosis.five_tone_read_model_schema_version
            == "five_tone_analysis_read_model_v3.1"
        )
        assert diagnosis.five_tone_read_model_checksum == (
            f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"
        )
        assert diagnosis.five_tone_generated_at is not None
        assert diagnosis.generation_spec_json["bpm"] == 66
        assert restored.bpm.value == 66
        assert diagnosis.preference_profile_id == "pref_formal"
        assert diagnosis.preference_version == 3
        assert diagnosis.preference_application_json == [
            {
                "field": "bpm",
                "before": 60,
                "after": 66,
                "applied": True,
                "reason_code": "preference_applied",
            }
        ]
        rag_run = audit_db.query(RagRetrievalRun).one()
        assert rag_run.rag_run_id == diagnosis.rag_run_id
        assert rag_run.status == "success"
        hit = audit_db.query(RagRetrievalHit).one()
        assert hit.rag_run_id == rag_run.rag_run_id
        assert "approved text" not in hit.text_ciphertext
        provider_run = audit_db.query(AiProviderRun).one()
        assert provider_run.provider_run_id == diagnosis.provider_run_id
        assert provider_run.status == "success"
        assert provider_run.error_code is None
        assert provider_run.request_hash.startswith("sha256:")
        assert provider_run.response_hash.startswith("sha256:")
    finally:
        audit_db.close()


def test_formal_router_reports_v31_readiness_failure_without_mock_fallback(
    db_session_factory, monkeypatch
):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.0,
                "heart": 1.0,
                "spleen": 0.0,
                "lung": 0.0,
                "kidney": 0.0,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: (_ for _ in ()).throw(
            agent_config.V31ReadinessFailure("DASHSCOPE_PROVIDER_NOT_CONFIGURED")
        ),
    )

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"readiness-{uuid.uuid4().hex}"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DASHSCOPE_PROVIDER_NOT_CONFIGURED"


def test_formal_router_persists_failed_provider_audit(
    db_session_factory, monkeypatch
):
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProviderFailure

    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.0,
                "heart": 1.0,
                "spleen": 0.0,
                "lung": 0.0,
                "kidney": 0.0,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    calls: list[str] = []
    dependencies = _dependencies(calls)

    async def fail_provider(**_kwargs):
        raise DiagnosisProviderFailure(
            "DIAGNOSIS_SCHEMA_INVALID",
            "辨证服务返回格式无效。",
            retryable=False,
        )

    dependencies.diagnosis_provider.acomplete_json = fail_provider
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: dependencies,
    )
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )

    response = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": f"failed-audit-{uuid.uuid4().hex}"},
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "DIAGNOSIS_SCHEMA_INVALID"
    audit_db = db_session_factory()
    try:
        diagnosis = audit_db.query(DiagnosisRun).one()
        assert diagnosis.status == "failed"
        assert diagnosis.abstained == 0
        assert diagnosis.rag_run_id == "rag_formal_entry"
        assert diagnosis.provider_run_id
        rag_run = audit_db.query(RagRetrievalRun).one()
        assert rag_run.status == "success"
        provider_run = audit_db.query(AiProviderRun).one()
        assert provider_run.status == "failed"
        assert provider_run.error_code == "DIAGNOSIS_SCHEMA_INVALID"
    finally:
        audit_db.close()


def test_formal_router_persists_abstained_retrieval_audit(
    db_session_factory, monkeypatch
):
    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.0,
                "heart": 1.0,
                "spleen": 0.0,
                "lung": 0.0,
                "kidney": 0.0,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    empty_rag = _rag_result().model_copy(
        update={
            "retrieval_id": "rag_formal_abstained",
            "status": "empty",
            "hits": [],
        }
    )
    calls: list[str] = []
    dependencies = _dependencies(calls, rag_result=empty_rag)
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: dependencies,
    )
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )

    response = client.post(
        "/api/v3/diagnoses",
        headers={
            "Authorization": headers["Authorization"],
            "Idempotency-Key": f"abstained-audit-{uuid.uuid4().hex}",
        },
        json=_diagnosis_body(session_id, assessment_id, 1),
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["status"] == "abstained"
    audit_db = db_session_factory()
    try:
        diagnosis = audit_db.query(DiagnosisRun).one()
        assert diagnosis.status == "abstained"
        assert diagnosis.abstained == 1
        assert diagnosis.abstain_reason == "RAG_EMPTY"
        assert diagnosis.rag_run_id == "rag_formal_abstained"
        assert diagnosis.provider_run_id is None
        rag_run = audit_db.query(RagRetrievalRun).one()
        assert rag_run.status == "empty"
        assert audit_db.query(AiProviderRun).count() == 0
    finally:
        audit_db.close()


def test_formal_router_persists_provider_abstain_and_replays_without_duplicate(
    db_session_factory, monkeypatch
):
    from backend.app.schemas.v3.diagnosis import DiagnosisProviderResponse

    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.0,
                "heart": 1.0,
                "spleen": 0.0,
                "lung": 0.0,
                "kidney": 0.0,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    calls: list[str] = []
    dependencies = _dependencies(calls)

    async def abstain_provider(**kwargs):
        del kwargs
        calls.append("qwen-abstain")
        return DiagnosisProviderResponse(
            status="abstained",
            candidate_tendencies=[],
            abstained=True,
            abstain_reason="NO_LEGAL_CANDIDATE",
        )

    dependencies.diagnosis_provider.acomplete_json = abstain_provider
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: dependencies,
    )
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )

    body = _diagnosis_body(session_id, assessment_id, 1)
    key = f"provider-abstain-{uuid.uuid4().hex}"
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

    assert first.status_code == 201, first.text
    assert first.json()["data"]["status"] == "abstained"
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == first.json()["data"]
    assert calls.count("qwen-abstain") == 1
    audit_db = db_session_factory()
    try:
        assert audit_db.query(DiagnosisRun).count() == 1
        provider_run = audit_db.query(AiProviderRun).one()
        assert provider_run.status == "abstained"
        assert provider_run.error_code == "NO_LEGAL_CANDIDATE"
        assert provider_run.attempts == 1
    finally:
        audit_db.close()


def test_formal_router_replays_failed_idempotency_result_without_rerunning_provider(
    db_session_factory, monkeypatch
):
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProviderFailure
    from backend.app.models.v3.session import V3IdempotencyRecord

    headers = _guest_headers()
    db = db_session_factory()
    session_id, user_pk, session_row = _setup_flow_session(db, headers)
    assessment_id = _seed_confirmed_assessment(
        db,
        user_pk=user_pk,
        session_row=session_row,
        organ_profile_json={
            "status": "available",
            "weights": {
                "liver": 0.0,
                "heart": 1.0,
                "spleen": 0.0,
                "lung": 0.0,
                "kidney": 0.0,
            },
            "score_semantics": "relative_evidence_distribution",
        },
    )
    db.close()

    calls = 0
    dependencies = _dependencies([])

    async def always_fail(**kwargs):
        nonlocal calls
        del kwargs
        calls += 1
        raise DiagnosisProviderFailure(
            "DIAGNOSIS_PROVIDER_TIMEOUT",
            "辨证服务响应超时。",
            retryable=True,
        )

    dependencies.diagnosis_provider.acomplete_json = always_fail
    monkeypatch.setattr(diagnosis_service, "_v31_real_mode", lambda: True)
    monkeypatch.setattr(
        agent_config,
        "get_v31_ai_pipeline_dependencies",
        lambda: dependencies,
    )
    monkeypatch.setattr(
        diagnosis_service,
        "_load_confirmed_user_state",
        lambda *args, **kwargs: _confirmed_state_for(session_id),
    )

    body = _diagnosis_body(session_id, assessment_id, 1)
    body["diagnosis_id"] = "diag_requested_id"
    key = f"retry-failed-{uuid.uuid4().hex}"
    first = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )
    retry = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": key},
        json=body,
    )
    conflict_body = {**body, "diagnosis_id": "different_diagnosis_id"}
    conflict = client.post(
        "/api/v3/diagnoses",
        headers={**headers, "Idempotency-Key": key},
        json=conflict_body,
    )

    assert first.status_code == 502
    assert first.json()["error"]["retryable"] is True
    assert retry.status_code == 502, retry.text
    assert retry.json() == first.json()
    assert conflict.status_code == 422, conflict.text
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert calls == 1
    audit_db = db_session_factory()
    try:
        assert audit_db.query(DiagnosisRun).count() == 1
        assert audit_db.query(DiagnosisRun).one().diagnosis_id == "diag_requested_id"
        assert audit_db.query(AiProviderRun).count() == 1
        record = audit_db.query(V3IdempotencyRecord).filter(
            V3IdempotencyRecord.idempotency_key == key
        ).one()
        assert record.status == "failed"
        assert record.response_json is not None
    finally:
        audit_db.close()

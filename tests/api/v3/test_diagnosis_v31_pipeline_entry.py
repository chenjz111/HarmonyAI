"""Formal V3.1 Router entry coverage at the approved dependency boundary.

These tests use fake transports/dependencies and are Mock integration tests;
they are deliberately not evidence of a real Embedding, Chroma, or Qwen
Smoke run.
"""

from types import SimpleNamespace
import uuid

from backend.app.core import agent_config
from backend.app.schemas.v3.common import Degradation
from backend.app.schemas.v3.diagnosis import IngestionManifest, RagHit, RagResult
from backend.app.schemas.v3.flow_v31 import ConfirmedUserState
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


def _dependencies(calls: list[str]):
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
            return _rag_result()

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

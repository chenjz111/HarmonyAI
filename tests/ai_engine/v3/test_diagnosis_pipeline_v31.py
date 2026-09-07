import pytest


def _rag_result():
    from backend.app.schemas.v3.common import Degradation
    from backend.app.schemas.v3.diagnosis import RagHit, RagResult

    return RagResult(
        retrieval_id="rag_1",
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


def _snapshot():
    return {
        "assessment_id": "asmt_1",
        "assessment_revision": 1,
        "knowledge_version": "medical_v3.1",
        "manifest_checksum": "sha256:manifest-v31",
        "organ_codes": ["heart", "spleen", "not-approved"],
        "claim_codes": ["unrefreshing_sleep", "not-approved"],
        "supporting_fact_ids": ["fact_2", "fact_1"],
        "contradicting_fact_ids": ["fact_3"],
        "approved_organ_codes": ["heart", "spleen"],
        "approved_claim_codes": ["unrefreshing_sleep"],
        "organ_weights": {"heart": 1.0},
    }


def test_diagnosis_query_is_canonical_and_uses_only_approved_codes():
    from backend.ai_engine.v3.diagnosis_pipeline import build_diagnosis_query

    first = build_diagnosis_query(_snapshot())
    second = build_diagnosis_query(
        {
            **_snapshot(),
            "organ_codes": ["spleen", "heart"],
            "supporting_fact_ids": ["fact_1", "fact_2"],
        }
    )

    assert first == second
    assert first.organ_codes == ["heart", "spleen"]
    assert first.claim_codes == ["unrefreshing_sleep"]
    assert first.supporting_fact_ids == ["fact_1", "fact_2"]
    assert first.contradicting_fact_ids == ["fact_3"]


def _provider_response(*, syndrome_code="syndrome_1", fact_id="fact_1", chunk_id="chunk_1"):
    from backend.app.schemas.v3.diagnosis import (
        DiagnosisProviderResponse,
        ProviderCandidateTendency,
    )

    return DiagnosisProviderResponse(
        status="success",
        candidate_tendencies=[
            ProviderCandidateTendency(
                syndrome_code=syndrome_code,
                display_name="safe tendency",
                relative_support=0.8,
                supporting_fact_ids=[fact_id],
                contradicting_fact_ids=[],
                knowledge_chunk_ids=[chunk_id],
                reasoning_summary="grounded summary",
            )
        ],
        abstained=False,
        abstain_reason=None,
    )


def test_diagnosis_response_requires_approved_syndrome_and_evidence_references():
    from backend.ai_engine.v3.diagnosis_pipeline import (
        DiagnosisPipelineFailure,
        validate_diagnosis_provider_response,
    )

    valid = validate_diagnosis_provider_response(
        _provider_response(),
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    assert valid == _provider_response()

    with pytest.raises(DiagnosisPipelineFailure, match="SYNDROME_NOT_APPROVED"):
        validate_diagnosis_provider_response(
            _provider_response(syndrome_code="invented"),
            allowed_syndrome_codes={"syndrome_1"},
            allowed_fact_ids={"fact_1"},
            allowed_chunk_ids={"chunk_1"},
        )

    with pytest.raises(DiagnosisPipelineFailure, match="FACT_REFERENCE_INVALID"):
        validate_diagnosis_provider_response(
            _provider_response(fact_id="fact_other"),
            allowed_syndrome_codes={"syndrome_1"},
            allowed_fact_ids={"fact_1"},
            allowed_chunk_ids={"chunk_1"},
        )

    with pytest.raises(DiagnosisPipelineFailure, match="CHUNK_REFERENCE_INVALID"):
        validate_diagnosis_provider_response(
            _provider_response(chunk_id="chunk_other"),
            allowed_syndrome_codes={"syndrome_1"},
            allowed_fact_ids={"fact_1"},
            allowed_chunk_ids={"chunk_1"},
        )


def test_diagnosis_response_rejects_duplicate_evidence_references():
    from backend.app.schemas.v3.diagnosis import DiagnosisProviderResponse, ProviderCandidateTendency
    from backend.ai_engine.v3.diagnosis_pipeline import (
        DiagnosisPipelineFailure,
        validate_diagnosis_provider_response,
    )

    duplicate = DiagnosisProviderResponse(
        status="success",
        candidate_tendencies=[
            ProviderCandidateTendency(
                syndrome_code="syndrome_1",
                display_name="safe tendency",
                relative_support=0.8,
                supporting_fact_ids=["fact_1", "fact_1"],
                contradicting_fact_ids=[],
                knowledge_chunk_ids=["chunk_1", "chunk_1"],
                reasoning_summary="grounded summary",
            )
        ],
        abstained=False,
        abstain_reason=None,
    )

    with pytest.raises(DiagnosisPipelineFailure, match="DUPLICATE_EVIDENCE_REFERENCE"):
        validate_diagnosis_provider_response(
            duplicate,
            allowed_syndrome_codes={"syndrome_1"},
            allowed_fact_ids={"fact_1"},
            allowed_chunk_ids={"chunk_1"},
        )


def test_diagnosis_response_rejects_evidence_direction_mismatch():
    from backend.ai_engine.v3.diagnosis_pipeline import (
        DiagnosisPipelineFailure,
        validate_diagnosis_provider_response,
    )

    with pytest.raises(DiagnosisPipelineFailure, match="EVIDENCE_DIRECTION_MISMATCH"):
        validate_diagnosis_provider_response(
            _provider_response(),
            allowed_syndrome_codes={"syndrome_1"},
            allowed_fact_ids={"fact_1"},
            allowed_chunk_ids={"chunk_1"},
            fact_directions={"fact_1": "contradicting"},
        )


def test_v31_pipeline_builds_the_frozen_provider_request():
    from backend.app.schemas.v3.diagnosis import DiagnosisProviderRequest
    from backend.ai_engine.v3.diagnosis_pipeline import _build_diagnosis_provider_request

    request = _build_diagnosis_provider_request(
        {
            **_snapshot(),
            "request_id": "req_1",
            "prompt_version": "diagnosis_prompt_v3.1",
            "medical_rule_version": "medical-rules-v3.1-r1",
            "facts": [
                {
                    "fact_evidence_id": "fact_1",
                    "claim_code": "unrefreshing_sleep",
                    "value": {"type": "frequency_0_4", "value": 3},
                    "direction": "supporting",
                    "time_window": "past_7_days",
                }
            ],
            "conflicts": [],
            "missing_information": [],
        },
        _rag_result(),
        allowed_syndrome_codes={"syndrome_1"},
    )

    assert isinstance(request, DiagnosisProviderRequest)
    assert request.request_id == "req_1"
    assert request.schema_version == "diagnosis_provider_v3.0"
    assert request.response_schema_version == "diagnosis_provider_response_v3.0"
    assert request.prompt_version == "diagnosis_prompt_v3.1"
    assert request.allowed_syndrome_codes == ["syndrome_1"]
    assert request.max_candidates == 3
    assert request.rag is not None
    assert request.rag.chunk_ids == ["chunk_1"]


def test_diagnosis_execution_fails_when_medical_rule_version_does_not_match():
    from backend.ai_engine.v3.diagnosis_pipeline import execute_diagnosis_provider

    class Provider:
        medical_rule_version = "medical-rules-v3.1-r0"

        async def acomplete_json(self, **kwargs):
            raise AssertionError("provider must not run with a stale medical rule asset")

    import asyncio

    result = asyncio.run(
        execute_diagnosis_provider(
            provider=Provider(),
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=_rag_result(),
            medical_rule_version="medical-rules-v3.1-r1",
        )
    )

    assert result.status == "failed"
    assert result.reason_code == "MEDICAL_RULE_VERSION_MISMATCH"


def test_diagnosis_provider_repairs_schema_once_then_accepts_grounded_response():
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider

    class Backend:
        def __init__(self):
            self.calls = []

        async def acomplete_json(self, system_prompt, user_prompt):
            self.calls.append((system_prompt, user_prompt))
            return (
                {"status": "success", "candidate_tendencies": [], "abstained": False, "abstain_reason": None}
                if len(self.calls) == 1
                else _provider_response().model_dump(mode="json")
            )

    backend = Backend()
    provider = DiagnosisProvider(
        backend=backend,
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )

    result = __import__("asyncio").run(
        provider.acomplete_json(
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=["fact_1"],
            rag_chunk_ids=["chunk_1"],
        )
    )

    assert result.status == "success"
    assert len(backend.calls) == 2
    assert "corrected" in backend.calls[1][0]


def test_diagnosis_provider_maps_provider_failure_without_user_text():
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider, DiagnosisProviderFailure

    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            raise TimeoutError("private user text must not escape")

    provider = DiagnosisProvider(
        backend=Backend(),
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )

    with pytest.raises(DiagnosisProviderFailure) as caught:
        __import__("asyncio").run(
            provider.acomplete_json(
                request={"assessment_id": "asmt_1", "revision": 1},
                facts=["fact_1"],
                rag_chunk_ids=["chunk_1"],
            )
        )

    assert caught.value.error_code == "DIAGNOSIS_PROVIDER_TIMEOUT"
    assert "private user text" not in str(caught.value)


def test_diagnosis_provider_maps_typed_provider_error_code_without_raw_message():
    from backend.ai_engine.sprint4_contracts import ProviderError, ProviderErrorCode
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider, DiagnosisProviderFailure

    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            raise ProviderError(
                ProviderErrorCode.RATE_LIMITED,
                True,
                "private user text must not escape",
            )

    provider = DiagnosisProvider(
        backend=Backend(),
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )

    with pytest.raises(DiagnosisProviderFailure) as caught:
        __import__("asyncio").run(
            provider.acomplete_json(
                request={"assessment_id": "asmt_1", "revision": 1},
                facts=["fact_1"],
                rag_chunk_ids=["chunk_1"],
            )
        )

    assert caught.value.error_code == "DIAGNOSIS_PROVIDER_RATE_LIMITED"
    assert caught.value.retryable is True
    assert "private user text" not in str(caught.value)


def test_diagnosis_provider_factory_requires_explicit_qwen_configuration():
    from backend.ai_engine.v3.diagnosis_provider import diagnosis_provider_from_environment

    assert (
        diagnosis_provider_from_environment(
            {},
            allowed_syndrome_codes={"syndrome_1"},
            allowed_fact_ids={"fact_1"},
            allowed_chunk_ids={"chunk_1"},
        )
        is None
    )
    provider = diagnosis_provider_from_environment(
        {
            "QWEN_BASE_URL": "https://qwen.example/v1",
            "QWEN_API_KEY": "secret",
            "QWEN_MODEL": "qwen-approved",
        },
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    assert provider is not None
    assert provider.backend.model == "qwen-approved"


def test_diagnosis_provider_factory_uses_dashscope_credentials_and_workspace():
    from backend.ai_engine.v3.diagnosis_provider import diagnosis_provider_from_environment

    provider = diagnosis_provider_from_environment(
        {
            "DASHSCOPE_API_KEY": "configured",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "DASHSCOPE_BASE_URL": "https://dashscope.example/compatible-mode/v1",
            "QWEN_MODEL": "qwen-approved",
        },
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )

    assert provider is not None
    assert provider.backend.model == "qwen-approved"
    assert provider.backend.extra_headers["X-DashScope-WorkSpace"] == "workspace-test"


def test_diagnosis_execution_does_not_call_qwen_when_rag_is_empty_or_degraded():
    from backend.app.schemas.v3.common import Degradation
    from backend.app.schemas.v3.diagnosis import RagResult
    from backend.ai_engine.v3.diagnosis_pipeline import execute_diagnosis_provider

    class Provider:
        calls = 0

        async def acomplete_json(self, **kwargs):
            self.calls += 1
            raise AssertionError("Qwen must not run without grounded RAG")

    provider = Provider()
    empty = RagResult(
        retrieval_id="rag_empty",
        status="empty",
        knowledge_version="medical_v3.1",
        embedding_version="text-embedding-v4@1024",
        retrieval_score_semantics="normalized_similarity",
        hits=[],
        degradation=Degradation(active=False, reason_codes=[]),
    )
    degraded = empty.model_copy(
        update={
            "retrieval_id": "rag_degraded",
            "status": "degraded",
            "degradation": Degradation(active=True, reason_codes=["RAG_UNAVAILABLE"]),
        }
    )

    import asyncio

    empty_result = asyncio.run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=empty,
        )
    )
    degraded_result = asyncio.run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=[],
            rag_result=degraded,
        )
    )

    assert empty_result.status == "abstained"
    assert empty_result.reason_code == "RAG_EMPTY"
    assert degraded_result.status == "failed"
    assert degraded_result.reason_code == "RAG_UNAVAILABLE"
    assert provider.calls == 0


def test_diagnosis_execution_passes_only_approved_rag_chunk_ids_to_qwen():
    from backend.app.schemas.v3.common import Degradation
    from backend.app.schemas.v3.diagnosis import (
        DiagnosisProviderResponse,
        ProviderCandidateTendency,
        RagHit,
        RagResult,
    )
    from backend.ai_engine.v3.diagnosis_pipeline import execute_diagnosis_provider

    class Provider:
        def __init__(self):
            self.kwargs = None

        async def acomplete_json(self, **kwargs):
            self.kwargs = kwargs
            return DiagnosisProviderResponse(
                status="success",
                candidate_tendencies=[
                    ProviderCandidateTendency(
                        syndrome_code="syndrome_1",
                        display_name="safe tendency",
                        relative_support=0.8,
                        supporting_fact_ids=["fact_1"],
                        contradicting_fact_ids=[],
                        knowledge_chunk_ids=["chunk_1"],
                        reasoning_summary="grounded summary",
                    )
                ],
                abstained=False,
                abstain_reason=None,
            )

    provider = Provider()
    rag = RagResult(
        retrieval_id="rag_1",
        status="success",
        knowledge_version="medical_v3.1",
        embedding_version="text-embedding-v4@1024",
        retrieval_score_semantics="normalized_similarity",
        hits=[
            RagHit(
                chunk_id="chunk_1",
                source_id="src_1",
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

    import asyncio

    result = asyncio.run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=["fact_1"],
            rag_result=rag,
        )
    )

    assert result.status == "success"
    assert result.response is not None
    assert provider.kwargs["rag_chunk_ids"] == ["chunk_1"]

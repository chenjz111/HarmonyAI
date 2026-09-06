import pytest


def _snapshot():
    return {
        "knowledge_version": "medical_v3.1",
        "manifest_checksum": "sha256:manifest-v31",
        "organ_codes": ["heart", "spleen", "not-approved"],
        "claim_codes": ["unrefreshing_sleep", "not-approved"],
        "supporting_fact_ids": ["fact_2", "fact_1"],
        "contradicting_fact_ids": ["fact_3"],
        "approved_organ_codes": ["heart", "spleen"],
        "approved_claim_codes": ["unrefreshing_sleep"],
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

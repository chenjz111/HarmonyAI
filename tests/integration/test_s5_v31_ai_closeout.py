import pytest


def _mapping():
    return {
        "schema_id": "five_tone_mapping_v3",
        "schema_version": "3.0.0",
        "organ_tone_weights": {
            "primary": {
                "heart": {"zhi": 0.7, "gong": 0.15, "yu": 0.15},
            }
        },
        "organ_tone_table": [
            {"tone": "jiao", "tone_cn": "角调"},
            {"tone": "zhi", "tone_cn": "徵调"},
            {"tone": "gong", "tone_cn": "宫调"},
            {"tone": "shang", "tone_cn": "商调"},
            {"tone": "yu", "tone_cn": "羽调"},
        ],
    }


def _manifest(review_status="approved"):
    from backend.app.schemas.v3.diagnosis import IngestionManifest

    raw = {
        "knowledge_version": "medical_v3.1",
        "embedding_provider": "aliyun",
        "embedding_model": "text-embedding-v4",
        "embedding_version": "text-embedding-v4@1024",
        "distance_metric": "cosine",
        "retrieval_score_semantics": "normalized_similarity",
        "minimum_score": 0.5,
        "chunk_count": 1,
        "manifest_checksum": "sha256:manifest-v31",
        "review_status": review_status,
    }
    return raw if review_status != "approved" else IngestionManifest(**raw)


def _chunk():
    from backend.app.schemas.v3.diagnosis import KnowledgeChunk

    return KnowledgeChunk(
        chunk_id="chunk_1",
        source_id="source_1",
        source_title="approved source",
        section="section",
        text="approved text",
        display_summary="approved summary",
        claim_codes=["unrefreshing_sleep"],
        organ_codes=["heart"],
        review_status="approved",
        medical_review_version="medical_v3.1-r1",
        knowledge_version="medical_v3.1",
        content_checksum="sha256:chunk-1",
    )


def test_closeout_keeps_pending_medical_corpus_out_of_production():
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        validate_production_corpus,
    )

    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_NOT_PRODUCTION_APPROVED"):
        validate_production_corpus(_manifest(review_status="pending"), [_chunk()])


def test_closeout_runs_grounded_agent2_then_public_agent3_without_internal_fields():
    from backend.app.schemas.v3.common import Degradation
    from backend.app.schemas.v3.diagnosis import (
        DiagnosisProviderResponse,
        ProviderCandidateTendency,
        RagHit,
        RagResult,
    )
    from backend.ai_engine.v3.agent3 import (
        build_generation_spec_v31,
        build_five_tone_analysis_v31,
        build_tone_profile_v31,
    )
    from backend.ai_engine.v3.diagnosis_pipeline import execute_diagnosis_provider
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider

    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            return {
                "status": "success",
                "candidate_tendencies": [
                    {
                        "syndrome_code": "syndrome_1",
                        "display_name": "safe tendency",
                        "relative_support": 0.8,
                        "supporting_fact_ids": ["fact_1"],
                        "contradicting_fact_ids": [],
                        "knowledge_chunk_ids": ["chunk_1"],
                        "reasoning_summary": "grounded summary",
                    }
                ],
                "abstained": False,
                "abstain_reason": None,
            }

    provider = DiagnosisProvider(
        backend=Backend(),
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    rag = RagResult(
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

    import asyncio

    execution = asyncio.run(
        execute_diagnosis_provider(
            provider=provider,
            request={"assessment_id": "asmt_1", "revision": 1},
            facts=["fact_1"],
            rag_result=rag,
        )
    )
    assert execution.status == "success"
    assert execution.response is not None

    profile = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 1.0},
        supporting_evidence_refs=["fact_1", "chunk_1"],
        mapping=_mapping(),
    )
    generation_spec = build_generation_spec_v31(
        profile=profile,
        parameter_rules={
            "schema_id": "music_generation_rules_v3.1",
            "schema_version": "test-approved-v1",
            "asset_version": "owner-approved-test-v1",
            "review_status": "approved",
            "secondary_goal_merge_policy": "primary_over_secondary_fill_missing",
            "default": {
                "bpm": 60,
                "instruments": ["古琴"],
                "ambience": ["细雨"],
                "duration_seconds": 180,
                "explanations": {
                    "bpm": "按已批准规则提供速度参考。",
                    "instruments": "按已批准规则提供配器参考。",
                    "ambience": "按已批准规则提供环境参考。",
                    "duration": "按已批准规则提供时长参考。",
                },
            },
            "goals": {
                "sleep": {},
                "relaxation": {},
                "emotion_regulation": {},
                "focus": {},
                "energy": {},
                "stress_relief": {},
                "other": {},
            },
        },
    )
    read_model = build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": "cus_1",
            "revision": 1,
            "content_checksum": "sha256:state",
        },
        confirmed_state="近期状态已确认。",
        state_tendency="整体偏向需要舒缓与稳定。",
        profile=profile,
        evidence_refs=["fact_1", "chunk_1"],
        mapping=_mapping(),
        generation_spec=generation_spec,
    )

    assert read_model.primary_tone.tone.value == "zhi"
    output = read_model.model_dump(mode="json")
    assert "provider" not in str(output).lower()
    assert "prompt" not in str(output).lower()
    assert "approved text" not in str(output)

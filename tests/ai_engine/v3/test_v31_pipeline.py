import asyncio

import pytest


def _confirmed_state():
    from backend.app.schemas.v3.flow_v31 import ConfirmedUserState

    return ConfirmedUserState.model_validate(
        {
            "schema_version": "confirmed_user_state_v3.1",
            "confirmed_user_state_id": "cus_1",
            "session_id": "sess_1",
            "source_mode": "questionnaire_only",
            "final_confirmed_summary_ref": None,
            "questionnaire_result_ref": {
                "questionnaire_result_id": "qres_1",
                "revision": 1,
                "content_checksum": "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031",
                "completion_status": "complete",
            },
            "user_goal_ref": None,
            "confirmed_state_text": "最近一周睡眠恢复感一般。",
            "normalized_projection": [
                {
                    "fact_id": "fact_1",
                    "claim_code": "unrefreshing_sleep",
                    "display_text": "睡后恢复感不足",
                    "source_refs": ["qres_1:q01"],
                }
            ],
            "revision": 2,
            "content_checksum": "sha256:state",
            "authority_status": "current",
            "confirmation_status": "confirmed",
            "confirmed_by": "user",
            "session_input_revision": 5,
            "created_at": "2026-09-07T01:04:00Z",
        }
    )


def _mapping():
    return {
        "schema_id": "five-tone_mapping_v3",
        "schema_version": "3.0.0",
        "organ_tone_weights": {
            "primary": {
                "heart": {"zhi": 1.0},
            }
        },
        "organ_tone_table": [
            {"tone": tone, "tone_cn": tone}
            for tone in ("jiao", "zhi", "gong", "shang", "yu")
        ],
    }


def _rules():
    return {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "test-approved-v1",
        "review_status": "approved",
        "default": {
            "bpm": 60,
            "instruments": ["古琴"],
            "ambience": ["细雨"],
            "duration_seconds": 900,
            "explanations": {
                "bpm": "按已批准规则提供速度参考。",
                "instruments": "按已批准规则提供配器参考。",
                "ambience": "按已批准规则提供环境参考。",
                "duration": "按已批准规则提供时长参考。",
            },
        },
        "goals": {
            "sleep": {
                "bpm": 50,
                "instruments": ["古琴", "箫"],
                "ambience": ["细雨"],
                "duration_seconds": 1200,
            }
        },
    }


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
        "organ_codes": ["heart"],
        "approved_organ_codes": ["heart"],
        "claim_codes": ["unrefreshing_sleep"],
        "approved_claim_codes": ["unrefreshing_sleep"],
        "supporting_fact_ids": ["fact_1"],
        "contradicting_fact_ids": [],
        "knowledge_version": "medical_v3.1",
        "manifest_checksum": "sha256:manifest",
        "top_k": 5,
        "organ_weights": {"heart": 1.0},
        "facts": [
            {
                "fact_evidence_id": "fact_1",
                "claim_code": "unrefreshing_sleep",
                "value": {"type": "frequency_0_4", "value": 3},
                "direction": "supporting",
                "time_window": "past_7_days",
            }
        ],
        "user_goal": {"primary_goal": "sleep"},
    }


def test_v31_pipeline_reaches_query_rag_qwen_agent3_and_public_read_model_without_user_goal():
    from backend.ai_engine.v3.agent3 import GenerationSpecV31
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
    from backend.ai_engine.v3.rag_store import RagStoreFailure
    from backend.ai_engine.v3.v31_pipeline import execute_v31_ai_pipeline

    del GenerationSpecV31, RagStoreFailure
    calls = []

    class Rag:
        def query(self, query):
            calls.append(("rag", query))
            return _rag_result()

    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            calls.append(("qwen", user_prompt))
            assert "user_goal" not in user_prompt
            assert "primary_goal" not in user_prompt
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
    result = asyncio.run(
        execute_v31_ai_pipeline(
            confirmed_user_state=_confirmed_state(),
            assessment_snapshot=_snapshot(),
            rag_store=Rag(),
            diagnosis_provider=provider,
            tone_mapping=_mapping(),
            generation_parameter_rules=_rules(),
            user_goal={"primary_goal": "sleep"},
        )
    )

    assert [kind for kind, _ in calls] == ["rag", "qwen"]
    assert result.diagnosis.status == "success"
    assert result.tone_profile.primary_tone.value == "zhi"
    assert result.generation_spec.secondary_tone is None
    assert result.generation_spec.bpm == 50
    assert result.read_model.generation.status == "ready"
    assert "次要音调规则尚未获批准" in result.read_model.generation.message
    assert "user_goal" not in result.diagnosis_request.model_dump(mode="json")


def test_v31_pipeline_rejects_non_current_or_unconfirmed_state_before_rag():
    from backend.ai_engine.v3.v31_pipeline import V31PipelineBlocked, execute_v31_ai_pipeline

    state = _confirmed_state().model_copy(update={"confirmation_status": "confirmed"})
    state_payload = state.model_dump(mode="json")
    state_payload["authority_status"] = "superseded"
    with pytest.raises(V31PipelineBlocked, match="CONFIRMED_USER_STATE_NOT_CURRENT"):
        asyncio.run(
            execute_v31_ai_pipeline(
                confirmed_user_state=state_payload,
                assessment_snapshot=_snapshot(),
                rag_store=None,
                diagnosis_provider=None,
                tone_mapping=_mapping(),
                generation_parameter_rules=_rules(),
            )
        )

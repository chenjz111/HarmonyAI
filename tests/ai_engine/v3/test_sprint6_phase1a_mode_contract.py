"""Sprint 6 Phase 1A — Backend Mode Contract & Fallback Semantics.

Covers the frozen Phase 1A acceptance minimum:

* genuine spleen/earth dominance still yields ``personalized_five_tone`` + gong
* an abstained diagnosis no longer yields gong (``basic_wellness``, no tone)
* ``integrated_regulation`` may legally carry ``primary_tone = null`` while
  retaining the full tone weights
* ``basic_wellness`` may legally carry ``primary_tone = null`` with no weights
* ``personalized_five_tone`` still forbids a null primary tone
* technical failures stay failed/blocked and are never relabelled as
  ``basic_wellness``
* unknown / missing / zero evidence never falls back to gong
* tone weights survive in ``integrated_regulation``

Phase 1A deliberately introduces **no dominance threshold** (margin/NTU
calibration stays Phase 1B); the only routing added here is the "no unique
maximum ⇒ no primary tone" rule required by 均衡 ≠ 宫.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from backend.ai_engine.v3.agent3 import (
    Agent3Blocked,
    build_five_tone_analysis_v31,
    build_generation_spec_v31,
    build_tone_profile_v31,
)
from backend.ai_engine.v3.v31_pipeline import V31PipelineBlocked, execute_v31_ai_pipeline
from backend.app.schemas.v3.common import ToneCode
from backend.app.schemas.v3.flow_v31 import (
    FiveToneAnalysisReadModel,
    ToneProfileBasisV31,
    ToneProfileV31,
)

TONE_CODES = ("jiao", "zhi", "gong", "shang", "yu")


# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #


def _mapping() -> dict[str, object]:
    return {
        "schema_id": "five-tone_mapping_v3",
        "schema_version": "3.0.0",
        "organ_tone_weights": {
            "primary": {
                "liver": {"jiao": 1.0},
                "heart": {"zhi": 1.0},
                "spleen": {"gong": 1.0},
                "lung": {"shang": 1.0},
                "kidney": {"yu": 1.0},
            }
        },
        "organ_tone_table": [
            {"tone": tone, "tone_cn": tone} for tone in TONE_CODES
        ],
    }


def _rules() -> dict[str, object]:
    return {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "test-approved-v1",
        "asset_version": "owner-approved-test-v1",
        "review_status": "approved",
        "secondary_goal_merge_policy": "primary_over_secondary_fill_missing",
        "default": {
            "bpm": 60,
            "instruments": ["guqin"],
            "ambience": ["water"],
            "duration_seconds": 180,
            "explanations": {
                "bpm": "approved bpm rule",
                "instruments": "approved instrument rule",
                "ambience": "approved ambience rule",
                "duration": "approved duration rule",
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
    }


def _profile(
    organ_weights: dict[str, float],
    *,
    diagnosis_status: str = "success",
) -> ToneProfileV31:
    return build_tone_profile_v31(
        diagnosis_id="diag_phase1a",
        diagnosis_status=diagnosis_status,
        organ_weights=organ_weights,
        supporting_evidence_refs=["fact_1"],
        mapping=_mapping(),
    )


def _basis() -> ToneProfileBasisV31:
    return ToneProfileBasisV31(
        diagnosis_id="diag_phase1a",
        diagnosis_revision=1,
        supporting_evidence_refs=["fact_1"],
    )


def _profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "tone_profile_v3.1",
        "regulation_mode": "personalized_five_tone",
        "weights": {
            "jiao": 0.1,
            "zhi": 0.1,
            "gong": 0.6,
            "shang": 0.1,
            "yu": 0.1,
        },
        "primary_tone": "gong",
        "secondary_tone": None,
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {
            "diagnosis_id": "diag_phase1a",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": ["fact_1"],
        },
    }
    payload.update(overrides)
    return payload


def _read_model_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "five_tone_analysis_read_model_v3.1",
        "confirmed_user_state_ref": {
            "confirmed_user_state_id": "cus_1",
            "revision": 1,
            "content_checksum": "sha256:cus",
        },
        "confirmed_state": "confirmed state",
        "state_tendency": "state tendency",
        "analysis_rationales": [
            {"summary": "basis summary", "evidence_refs": ["fact_1"]}
        ],
        "regulation_mode": "personalized_five_tone",
        "tone_weights": {
            "jiao": 0.1,
            "zhi": 0.1,
            "gong": 0.6,
            "shang": 0.1,
            "yu": 0.1,
        },
        "primary_tone": {
            "tone": "gong",
            "display_name": "gong",
            "explanation": "primary tone",
        },
        "secondary_tone": None,
        "bpm": {"value": 60, "explanation": "approved bpm"},
        "instruments": {"values": ["guqin"], "explanation": "approved instruments"},
        "ambience": {"values": ["water"], "explanation": "approved ambience"},
        "duration": {"seconds": 180, "explanation": "approved duration"},
        "generation": {"status": "ready", "message": "ready"},
        "disclaimer": "reference only",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# 1. mode-scoped contract
# --------------------------------------------------------------------------- #


def test_personalized_five_tone_requires_a_primary_tone_and_weights():
    ToneProfileV31.model_validate(_profile_payload())

    with pytest.raises(ValidationError, match="requires a primary tone"):
        ToneProfileV31.model_validate(_profile_payload(primary_tone=None))

    with pytest.raises(ValidationError, match="requires tone weights"):
        ToneProfileV31.model_validate(_profile_payload(weights=None))


def test_integrated_regulation_allows_null_primary_and_keeps_weights():
    profile = ToneProfileV31.model_validate(
        _profile_payload(
            regulation_mode="integrated_regulation",
            primary_tone=None,
            weights={tone: 0.2 for tone in TONE_CODES},
        )
    )
    assert profile.primary_tone is None
    assert profile.weights is not None and len(profile.weights) == 5

    # integrated may not claim a primary tone, and must keep its weights
    with pytest.raises(ValidationError, match="must not carry a primary tone"):
        ToneProfileV31.model_validate(
            _profile_payload(regulation_mode="integrated_regulation")
        )
    with pytest.raises(ValidationError, match="must retain tone weights"):
        ToneProfileV31.model_validate(
            _profile_payload(
                regulation_mode="integrated_regulation",
                primary_tone=None,
                weights=None,
            )
        )


def test_basic_wellness_allows_null_primary_without_fabricated_weights():
    profile = ToneProfileV31.model_validate(
        _profile_payload(
            regulation_mode="basic_wellness", primary_tone=None, weights=None
        )
    )
    assert profile.primary_tone is None
    assert profile.weights is None

    # neutral (uniform) weights are tolerated, a tone-shaped distribution is not
    ToneProfileV31.model_validate(
        _profile_payload(
            regulation_mode="basic_wellness",
            primary_tone=None,
            weights={tone: 0.2 for tone in TONE_CODES},
        )
    )
    with pytest.raises(ValidationError, match="must be neutral"):
        ToneProfileV31.model_validate(
            _profile_payload(regulation_mode="basic_wellness", primary_tone=None)
        )
    with pytest.raises(ValidationError, match="must not carry a primary tone"):
        ToneProfileV31.model_validate(
            _profile_payload(
                regulation_mode="basic_wellness", primary_tone="gong", weights=None
            )
        )


def test_read_model_exposes_mode_and_nullable_primary_tone():
    personalized = FiveToneAnalysisReadModel.model_validate(_read_model_payload())
    assert personalized.regulation_mode == "personalized_five_tone"
    assert personalized.primary_tone is not None
    assert personalized.tone_weights is not None

    integrated = FiveToneAnalysisReadModel.model_validate(
        _read_model_payload(
            regulation_mode="integrated_regulation",
            primary_tone=None,
            tone_weights={tone: 0.2 for tone in TONE_CODES},
        )
    )
    assert integrated.primary_tone is None
    assert integrated.tone_weights is not None

    basic = FiveToneAnalysisReadModel.model_validate(
        _read_model_payload(
            regulation_mode="basic_wellness",
            primary_tone=None,
            tone_weights=None,
        )
    )
    assert basic.primary_tone is None
    assert basic.tone_weights is None

    with pytest.raises(ValidationError, match="must not present a primary tone"):
        FiveToneAnalysisReadModel.model_validate(
            _read_model_payload(regulation_mode="basic_wellness")
        )
    with pytest.raises(ValidationError, match="requires a primary tone"):
        FiveToneAnalysisReadModel.model_validate(
            _read_model_payload(
                regulation_mode="personalized_five_tone", primary_tone=None
            )
        )


def test_legacy_profile_without_regulation_mode_is_read_compatibly():
    legacy = _profile_payload()
    legacy.pop("regulation_mode")
    assert (
        ToneProfileV31.model_validate(legacy).regulation_mode
        == "personalized_five_tone"
    )

    legacy_read_model = _read_model_payload()
    legacy_read_model.pop("regulation_mode")
    assert (
        FiveToneAnalysisReadModel.model_validate(legacy_read_model).regulation_mode
        == "personalized_five_tone"
    )


# --------------------------------------------------------------------------- #
# 2. genuine dominance keeps personalized modes (cases A / B / C)
# --------------------------------------------------------------------------- #


def test_genuine_spleen_dominance_still_yields_personalized_gong():
    profile = _profile({"spleen": 0.7, "liver": 0.1, "heart": 0.1, "lung": 0.05, "kidney": 0.05})
    assert profile.regulation_mode == "personalized_five_tone"
    assert profile.primary_tone is ToneCode.gong
    assert profile.weights is not None


@pytest.mark.parametrize(
    ("organ", "tone"),
    [("liver", "jiao"), ("heart", "zhi"), ("lung", "shang"), ("kidney", "yu")],
)
def test_genuine_single_organ_dominance_keeps_personalized_mode(organ, tone):
    weights = {name: 0.05 for name in ("liver", "heart", "spleen", "lung", "kidney")}
    weights[organ] = 0.8
    profile = _profile(weights)
    assert profile.regulation_mode == "personalized_five_tone"
    assert profile.primary_tone.value == tone


# --------------------------------------------------------------------------- #
# 3. balanced / tied profile never becomes an arbitrary tone (case D)
# --------------------------------------------------------------------------- #


def test_exact_tie_is_integrated_regulation_without_primary_tone():
    profile = _profile({name: 0.2 for name in ("liver", "heart", "spleen", "lung", "kidney")})
    assert profile.regulation_mode == "integrated_regulation"
    assert profile.primary_tone is None
    assert profile.secondary_tone is None
    assert profile.weights is not None
    # balanced distribution is retained and still user-meaningful
    assert len(set(round(value, 6) for value in profile.weights.values())) == 1


# --------------------------------------------------------------------------- #
# 4. abstain / insufficient never fabricate a tone (cases E / G)
# --------------------------------------------------------------------------- #


def test_abstained_diagnosis_is_basic_wellness_without_any_tone():
    profile = _profile({"heart": 1.0}, diagnosis_status="abstained")
    assert profile.regulation_mode == "basic_wellness"
    assert profile.primary_tone is None
    assert profile.secondary_tone is None
    assert profile.weights is None


def test_zero_organ_evidence_is_an_explicit_gate_not_gong():
    with pytest.raises(Agent3Blocked, match="INSUFFICIENT_ORGAN_EVIDENCE"):
        _profile({name: 0.0 for name in ("liver", "heart", "spleen", "lung", "kidney")})


def test_unknown_organ_or_malformed_mapping_never_falls_back_to_gong():
    with pytest.raises(Agent3Blocked, match="INVALID_MAPPING"):
        build_tone_profile_v31(
            diagnosis_id="diag_phase1a",
            organ_weights={"unknown_organ": 1.0},
            supporting_evidence_refs=["fact_1"],
            mapping=_mapping(),
        )
    broken = _mapping()
    broken["organ_tone_weights"] = {"primary": {"spleen": {"not_a_tone": 1.0}}}  # type: ignore[index]
    with pytest.raises(Agent3Blocked, match="INVALID_MAPPING"):
        build_tone_profile_v31(
            diagnosis_id="diag_phase1a",
            organ_weights={"spleen": 1.0},
            supporting_evidence_refs=["fact_1"],
            mapping=broken,
        )


def test_missing_evidence_references_are_explicitly_blocked():
    with pytest.raises(Agent3Blocked, match="INSUFFICIENT_EVIDENCE_REFERENCES"):
        build_tone_profile_v31(
            diagnosis_id="diag_phase1a",
            organ_weights={"spleen": 1.0},
            supporting_evidence_refs=[],
            mapping=_mapping(),
        )


# --------------------------------------------------------------------------- #
# 5. generated spec + public read model for all three modes
# --------------------------------------------------------------------------- #


def _read_model_for(profile: ToneProfileV31) -> FiveToneAnalysisReadModel:
    spec = build_generation_spec_v31(profile=profile, parameter_rules=_rules())
    assert spec.regulation_mode == profile.regulation_mode
    return build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": "cus_1",
            "revision": 1,
            "content_checksum": "sha256:cus",
        },
        confirmed_state="confirmed state",
        state_tendency="state tendency",
        profile=profile,
        evidence_refs=["fact_1"],
        mapping=_mapping(),
        generation_spec=spec,
    )


def test_personalized_read_model_carries_primary_tone_and_weights():
    read_model = _read_model_for(_profile({"spleen": 0.8, "liver": 0.05, "heart": 0.05, "lung": 0.05, "kidney": 0.05}))
    assert read_model.regulation_mode == "personalized_five_tone"
    assert read_model.primary_tone is not None
    assert read_model.primary_tone.tone is ToneCode.gong
    assert read_model.tone_weights is not None


def test_integrated_read_model_has_no_primary_tone_but_keeps_weights():
    read_model = _read_model_for(
        _profile({name: 0.2 for name in ("liver", "heart", "spleen", "lung", "kidney")})
    )
    assert read_model.regulation_mode == "integrated_regulation"
    assert read_model.primary_tone is None
    assert read_model.tone_weights is not None
    assert "无单一" in read_model.generation.message or "未形成单一" in read_model.generation.message


def test_basic_wellness_read_model_claims_no_tone():
    read_model = _read_model_for(_profile({"heart": 1.0}, diagnosis_status="abstained"))
    assert read_model.regulation_mode == "basic_wellness"
    assert read_model.primary_tone is None
    assert read_model.tone_weights is None
    # approved non-tone parameters are still prepared
    assert read_model.generation.status == "ready"
    assert read_model.bpm.value == 60


# --------------------------------------------------------------------------- #
# 6. technical failures are not modes
# --------------------------------------------------------------------------- #


def test_invalid_diagnosis_status_is_a_blocked_technical_state():
    with pytest.raises(Agent3Blocked, match="DIAGNOSIS_NOT_AVAILABLE"):
        _profile({"spleen": 1.0}, diagnosis_status="not_a_status")


def test_provider_failure_raises_pipeline_block_not_basic_wellness():
    from backend.ai_engine.providers import ProviderError
    from backend.ai_engine.sprint4_contracts import ProviderErrorCode
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider

    class Rag:
        manifest = None
        chunk_checksums = {}

        def query(self, query):
            del query
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

    class Backend:
        async def acomplete_json(self, system_prompt, user_prompt):
            del system_prompt, user_prompt
            raise ProviderError(
                ProviderErrorCode.NOT_CONFIGURED, False, "provider not configured"
            )

    provider = DiagnosisProvider(
        backend=Backend(),
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    with pytest.raises(V31PipelineBlocked) as error:
        asyncio.run(
            execute_v31_ai_pipeline(
                confirmed_user_state=_confirmed_state(),
                assessment_snapshot=_snapshot(),
                rag_store=Rag(),
                diagnosis_provider=provider,
                tone_mapping=_mapping(),
                generation_parameter_rules=_rules(),
            )
        )
    # a technical failure is a blocking error, never a basic_wellness result
    assert error.value.error_code
    assert "basic_wellness" not in error.value.error_code


def test_same_input_is_repeatable_for_mode_primary_and_weights():
    weights = {"spleen": 0.7, "liver": 0.1, "heart": 0.1, "lung": 0.05, "kidney": 0.05}
    first = _profile(weights)
    second = _profile(weights)
    assert first.regulation_mode == second.regulation_mode
    assert first.primary_tone == second.primary_tone
    assert first.weights == second.weights

    tied = {name: 0.2 for name in ("liver", "heart", "spleen", "lung", "kidney")}
    assert _profile(tied).regulation_mode == _profile(tied).regulation_mode


# --------------------------------------------------------------------------- #
# 7. prescription fallback semantics (service level)
# --------------------------------------------------------------------------- #


def test_conservative_wellness_spec_has_no_fabricated_tone_and_keeps_parameters():
    from backend.app.services.v3.prescription_service import _conservative_wellness_spec

    spec = _conservative_wellness_spec("diag_1", 1, None, None)
    assert spec.tone_profile.regulation_mode == "basic_wellness"
    assert spec.tone_profile.primary_tone is None
    assert spec.tone_profile.weights is None
    # approved deterministic non-tone parameters are still present
    assert spec.bpm == 62
    assert spec.instruments == ["guqin"]
    assert spec.duration_seconds == 180


# --------------------------------------------------------------------------- #
# 8. minimal pipeline fixtures (technical-failure test only)
# --------------------------------------------------------------------------- #


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
            "confirmed_state_text": "confirmed state text",
            "normalized_projection": [
                {
                    "fact_id": "fact_1",
                    "claim_code": "unrefreshing_sleep",
                    "display_text": "unrefreshing sleep",
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


def _snapshot() -> dict[str, object]:
    return {
        "assessment_id": "asmt_phase1a",
        "assessment_revision": 1,
        "diagnosis_id": "diag_phase1a",
        "diagnosis_revision": 1,
        "organ_codes": ["spleen"],
        "approved_organ_codes": ["spleen"],
        "claim_codes": ["unrefreshing_sleep"],
        "approved_claim_codes": ["unrefreshing_sleep"],
        "supporting_fact_ids": ["fact_1"],
        "contradicting_fact_ids": [],
        "knowledge_version": "medical_v3.1",
        "manifest_checksum": "sha256:manifest",
        "top_k": 5,
        "organ_weights": {
            "spleen": 0.8,
            "liver": 0.05,
            "heart": 0.05,
            "lung": 0.05,
            "kidney": 0.05,
        },
        "facts": [
            {
                "fact_evidence_id": "fact_1",
                "claim_code": "unrefreshing_sleep",
                "value": {"type": "frequency_0_4", "value": 3},
                "direction": "supporting",
                "time_window": "past_7_days",
            }
        ],
        "state_tendency": "state tendency",
        "confirmed_state_text": "confirmed state text",
        "medical_rule_version": "medical_v3.1",
        "embedding_version": "text-embedding-v4@1024",
        "retrieval_score_semantics": "normalized_similarity",
    }

"""Offline regressions for evidence-bound Player explanations and compatibility."""

import asyncio
import json

import pytest
from pydantic import ValidationError

from backend.app.schemas.v3.flow_v31 import FiveToneAnalysisReadModelV33
from tests.ai_engine.v3.test_agent3_v31 import _preference_read_model
from tests.ai_engine.v3.test_phase4_evidence_kernel_v31 import _Backend, _Rag, _payload
from tests.ai_engine.v3.test_v31_pipeline import _confirmed_state, _mapping, _rules, _snapshot
from tests.sprint6_phase1b_fixtures import synthetic_evidence, organ_mapping


@pytest.mark.parametrize("field", ["bpm", "instruments", "ambience"])
@pytest.mark.parametrize("missing", [True, False])
def test_modern_parameter_explanation_may_be_omitted_or_null(field, missing):
    payload = _preference_read_model().model_dump(mode="json")
    if missing:
        payload[field].pop("explanation")
    else:
        payload[field]["explanation"] = None
    parsed = FiveToneAnalysisReadModelV33.model_validate(payload)
    assert getattr(parsed, field).explanation is None
    dumped = parsed.model_dump(mode="json", exclude_none=True)
    assert "explanation" not in dumped[field]
    restored = FiveToneAnalysisReadModelV33.model_validate_json(parsed.model_dump_json())
    assert getattr(restored, field).explanation is None
    assert dumped[field]["value" if field == "bpm" else "values"]


def test_nonempty_historical_v33_payload_roundtrips_without_checksum_change():
    from backend.ai_engine.v3.grounding import canonical_checksum

    payload = _preference_read_model().model_dump(mode="json")
    for field in ("bpm", "instruments", "ambience"):
        payload[field]["explanation"] = "历史已持久化的解释。"
    checksum = canonical_checksum(payload)
    restored = FiveToneAnalysisReadModelV33.model_validate_json(json.dumps(payload))
    assert restored.model_dump(mode="json") == payload
    assert canonical_checksum(restored.model_dump(mode="json")) == checksum


@pytest.mark.parametrize("field", ["bpm", "instruments", "ambience"])
def test_modern_missing_reason_does_not_accept_empty_or_whitespace(field):
    payload = _preference_read_model().model_dump(mode="json")
    for invalid in ("", "   "):
        payload[field]["explanation"] = invalid
        with pytest.raises(ValidationError):
            FiveToneAnalysisReadModelV33.model_validate(payload)


def test_v32_missing_parameter_explanation_has_same_bounded_compatibility():
    from backend.app.schemas.v3.flow_v31 import FiveToneAnalysisReadModel
    payload = _preference_read_model().model_dump(mode="json")
    payload["schema_version"] = "five_tone_analysis_read_model_v3.2"
    for audit_field in ("dominant_organ", "dominance_decision", "decision_reason_code"):
        payload.pop(audit_field)
    for field in ("bpm", "instruments", "ambience"):
        payload[field].pop("explanation")
    read = FiveToneAnalysisReadModel.model_validate(payload)
    assert read.bpm.explanation is None
    assert FiveToneAnalysisReadModel.model_validate_json(read.model_dump_json()) == read


def test_unauthorized_explanations_and_parameter_values_remain_required():
    from backend.app.schemas.v3.flow_v31 import (
        BpmExplanation, ListParameterExplanation, PublicToneExplanation,
        ModeExplanation, EnergyExplanation, StructureExplanation,
    )

    for model, payload in [
        (BpmExplanation, {"value": 60}),
        (ListParameterExplanation, {"values": ["古琴"]}),
        (PublicToneExplanation, {"tone": "gong", "display_name": "宫调"}),
        (ModeExplanation, {"label": "基础舒缓"}),
        (EnergyExplanation, {"value": "平稳舒缓"}),
        (StructureExplanation, {"value": "渐入"}),
    ]:
        with pytest.raises(ValidationError):
            model.model_validate(payload)
    payload = _preference_read_model().model_dump(mode="json")
    for field, value_key in [("bpm", "value"), ("instruments", "values"), ("ambience", "values")]:
        invalid = json.loads(json.dumps(payload))
        invalid[field].pop(value_key)
        with pytest.raises(ValidationError):
            FiveToneAnalysisReadModelV33.model_validate(invalid)


def _run(*, historical=True, mutate=None, goal=None, rules=None):
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
    from backend.ai_engine.v3.v31_pipeline import execute_v31_ai_pipeline
    from backend.app.services.v3.organ_dominance_service import build_organ_aggregation_snapshot
    from backend.app.services.v3.knowledge_assets import load_claim_dictionary

    evidence, links = synthetic_evidence({"spleen": 1.8, "liver": 1.5})
    _, claims = load_claim_dictionary()
    from backend.app.schemas.v3.assessment import FactEvidence
    evidence = [FactEvidence.model_validate({**item.model_dump(),
        "assessment_id": "asmt_1",
        "display_name": claims[item.claim_code].display_name,
        "time_window": "source_recorded" if historical else "past_7_days",
        "source_refs": [dict(source_type="document" if historical else "questionnaire",
                             source_id="doc_2024" if historical else "qres_1", span_ref="record:2024-08-21" if historical else None)],
    }) for item in evidence]
    if mutate:
        evidence, links = mutate(evidence, links)
    snapshot = _snapshot()
    snapshot["organ_aggregation"] = build_organ_aggregation_snapshot(evidence, links, organ_mapping())
    snapshot["organ_weights"] = snapshot["organ_aggregation"].normalized_weights_by_organ
    snapshot["supporting_fact_ids"] = [e.fact_evidence_id for e in evidence if e.direction == "supporting"]
    snapshot["contradicting_fact_ids"] = [e.fact_evidence_id for e in evidence if e.direction == "contradicting"]
    snapshot["facts"] = [dict(fact_evidence_id=e.fact_evidence_id, claim_code=e.claim_code,
                              value=e.value.model_dump(), direction=e.direction.value, time_window=e.time_window) for e in evidence]
    payload = _payload(display_name="unused", support=.8, reasoning="provider text must not escape")
    payload["candidate_tendencies"][0]["supporting_fact_ids"] = []
    provider = DiagnosisProvider(backend=_Backend(payload), allowed_syndrome_codes={"syd_005"},
                                 allowed_fact_ids={e.fact_evidence_id for e in evidence}, allowed_chunk_ids={"chunk_1"})
    return asyncio.run(execute_v31_ai_pipeline(
        confirmed_user_state=_confirmed_state(), assessment_snapshot=snapshot,
        rag_store=_Rag(), diagnosis_provider=provider, tone_mapping=_mapping(),
        generation_parameter_rules=rules or _rules(), user_goal=goal,
    ))


def test_historical_state_and_personalized_reason_use_actual_contributing_facts():
    result = _run()
    read = result.read_model
    assert read.regulation_mode == "personalized_five_tone"
    assert read.primary_tone.tone == "gong"
    assert "思虑" in read.state_tendency
    assert "资料" in read.state_tendency
    assert "近期" not in read.state_tendency
    assert "当前症状" not in read.state_tendency
    rationale = read.analysis_rationales[0]
    assert "思虑" in rationale.summary and "脾" in rationale.summary
    assert "宫" in read.primary_tone.explanation
    assert "脾" in read.primary_tone.explanation
    assert set(rationale.evidence_refs) <= {"fev_spleen_0", "fev_spleen_1"}
    for text in (read.state_tendency, rationale.summary, read.mode_explanation.explanation, read.primary_tone.explanation):
        assert "已根据" not in text
        assert "保持一致" not in text
        assert "provider text" not in text


def test_recent_questionnaire_state_remains_recent():
    assert "近七天" in _run(historical=False).read_model.state_tendency


def test_missing_dominant_public_basis_is_disclosed_once_without_changing_selection():
    from backend.ai_engine.v3.agent3 import build_five_tone_analysis_v31
    from backend.ai_engine.v3.public_explanation import PublicFact
    from pathlib import Path
    rules = json.loads((Path(__file__).resolve().parents[3] / "knowledge/v3/music-generation-rules-v3.1.json").read_text(encoding="utf-8"))
    result = _run(goal={"primary_goal": "energy", "secondary_goal": "emotion_regulation"}, rules=rules)
    read = result.read_model
    # A different organ remains publicly eligible; unknown/negated dominant
    # facts have already been excluded by the DB-owned public eligibility gate.
    rebuilt = build_five_tone_analysis_v31(
        confirmed_user_state_ref=read.confirmed_user_state_ref.model_dump(),
        confirmed_state=read.confirmed_state, state_tendency="资料记录中的胁肋不适。",
        profile=result.tone_profile, mapping=_mapping(), generation_spec=result.generation_spec,
        evidence_refs=["fev_liver"],
        dominance_decision=read.dominance_decision,
        public_evidence=[PublicFact("fev_liver", "flank_discomfort", "胁肋不适", "source_recorded", ("liver",))],
        generation_parameter_rules=rules, user_goal={"primary_goal": "energy", "secondary_goal": "emotion_regulation"},
    )
    limitation = "缺少可公开引用的具体状态依据"
    assert limitation in rebuilt.analysis_rationales[0].summary
    assert limitation not in rebuilt.mode_explanation.explanation
    assert limitation not in rebuilt.primary_tone.explanation
    assert "脾对应宫调" in rebuilt.primary_tone.explanation
    assert rebuilt.confirmed_state == read.confirmed_state
    assert rebuilt.primary_tone.tone == "gong"
    assert rebuilt.bpm.value == 84 and rebuilt.instruments.values == ["笛"]
    assert rebuilt.ambience.values == ["微风"]


def test_energy_design_explains_arrangement_not_only_goal_parameter_lookup():
    from pathlib import Path
    rules = json.loads((Path(__file__).resolve().parents[3] / "knowledge/v3/music-generation-rules-v3.1.json").read_text(encoding="utf-8"))
    read = _run(goal={"primary_goal": "energy", "secondary_goal": "emotion_regulation"}, rules=rules).read_model
    assert "对应的 84 BPM 节奏选项" not in read.bpm.explanation
    assert "轻快有活力" in read.bpm.explanation
    assert "主要音色" in read.instruments.explanation
    assert "背景" in read.ambience.explanation and "轻柔" in read.ambience.explanation
    for parameter in (read.bpm, read.instruments, read.ambience):
        assert "希望" in parameter.explanation or "用于" in parameter.explanation
        assert "疗效" not in parameter.explanation and "症状" not in parameter.explanation


def test_parameter_reason_requires_selected_rule_not_mode_consistency():
    read = _run(goal={"primary_goal": "sleep"}).read_model
    assert read.bpm.value == 50
    assert "助眠" in read.bpm.explanation
    assert "50" in read.bpm.explanation
    assert "保持一致" not in read.bpm.explanation
    # Default and same-as-default rows provide no case-specific justification.
    assert read.ambience.explanation is None
    neutral = _run().read_model
    assert neutral.bpm.explanation is None
    assert neutral.instruments.explanation is None
    assert neutral.ambience.explanation is None


def test_negative_rejected_and_unconfirmed_evidence_never_become_positive_reasons():
    from backend.app.schemas.v3.assessment import FactEvidence

    def mutate(evidence, links):
        template = evidence[0].model_dump()
        extras = []
        for index, change in enumerate([
            {"claim_code": "eye_discomfort", "value": {"type": "boolean", "value": False}},
            {"claim_code": "throat_cough", "direction": "contradicting"},
            {"claim_code": "fear_tendency", "confirmation_status": "rejected"},
            {"claim_code": "sadness_tendency", "confirmation_status": "unconfirmed"},
        ]):
            extras.append(FactEvidence.model_validate({**template, "fact_id": f"unsafe_{index}",
                "fact_evidence_id": f"unsafe_{index}", **change}))
        return evidence + extras, links

    read = _run(mutate=mutate).read_model
    public_text = read.state_tendency + read.analysis_rationales[0].summary + read.primary_tone.explanation
    for excluded in ("目干", "咳", "恐惧", "悲伤"):
        assert excluded not in public_text
    assert not any(ref.startswith("unsafe_") for ref in read.analysis_rationales[0].evidence_refs)


def test_basic_has_specific_limit_and_no_invented_organ_or_tone():
    from backend.ai_engine.v3.v31_pipeline import build_v31_legal_abstain
    result = build_v31_legal_abstain(
        confirmed_user_state=_confirmed_state(), assessment_snapshot=_snapshot(),
        tone_mapping=_mapping(), generation_parameter_rules=_rules(), abstain_reason="EVIDENCE_INSUFFICIENT")
    read = result.read_model
    assert read.primary_tone is None and read.secondary_tone is None and read.dominant_organ is None
    assert "基础舒缓" in read.analysis_rationales[0].summary
    assert "依据不足" in read.analysis_rationales[0].summary
    assert "综合调适" not in read.analysis_rationales[0].summary


def test_changed_preference_cannot_retain_reason_for_a_different_parameter():
    from backend.app.services.v3.agent3_preference_policy import apply_preference_policy
    from tests.ai_engine.v3.test_agent3_v31 import _preference

    read = _run(goal={"primary_goal": "sleep"}).read_model
    assert "50" in read.bpm.explanation
    updated, _ = apply_preference_policy(read, _preference(preferred_bpm_range={"min": 80, "max": 80, "weight": 1.0}))
    assert updated.bpm.value == 80
    assert updated.bpm.explanation is None
    assert updated.analysis_rationales == read.analysis_rationales


def test_parameter_provenance_must_match_actual_value_and_internal_reason():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31, build_tone_profile_v31
    from backend.ai_engine.v3.public_explanation import parameter_explanations
    from tests.ai_engine.v3.test_agent3_v31 import _decision

    profile = build_tone_profile_v31(diagnosis_id="diag_verify", organ_weights={"heart": 1},
        supporting_evidence_refs=["f1"], mapping=_mapping(), dominance_decision=_decision())
    rules = _rules()
    spec = build_generation_spec_v31(profile=profile, parameter_rules=rules, user_goal={"primary_goal": "sleep"})
    payload = spec.model_dump()
    payload["bpm"] = 80
    changed = type(spec).model_validate(payload)
    assert parameter_explanations(spec=changed, profile=profile, rules=rules, user_goal={"primary_goal": "sleep"})["bpm"] is None
    assert all(value is None for value in parameter_explanations(spec=spec, profile=profile, rules=None, user_goal={"primary_goal": "sleep"}).values())
    payload = spec.model_dump()
    payload["explanations"]["bpm"] = "unverified rationale"
    changed = type(spec).model_validate(payload)
    assert parameter_explanations(spec=changed, profile=profile, rules=rules, user_goal={"primary_goal": "sleep"})["bpm"] is None


def test_approved_goal_rules_explain_actual_instrument_and_ambience_only():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31, build_tone_profile_v31
    from backend.ai_engine.v3.public_explanation import parameter_explanations
    from backend.app.services.v3.knowledge_assets import load_configured_music_generation_rules
    from tests.ai_engine.v3.test_agent3_v31 import _decision
    profile = build_tone_profile_v31(diagnosis_id="diag_goal", organ_weights={"heart": 1},
        supporting_evidence_refs=["f1"], mapping=_mapping(), dominance_decision=_decision())
    rules = load_configured_music_generation_rules()
    for goal, instrument, ambience in [("emotion_regulation", "琵琶", "微风"), ("relaxation", None, "溪流")]:
        spec = build_generation_spec_v31(profile=profile, parameter_rules=rules, user_goal={"primary_goal": goal})
        reasons = parameter_explanations(spec=spec, profile=profile, rules=rules, user_goal={"primary_goal": goal})
        assert ambience in reasons["ambience"]
        if instrument:
            assert instrument in reasons["instruments"]
        else:
            assert reasons["instruments"] is None
        assert reasons["bpm"] is None


def test_secondary_explanation_uses_existing_mapping_without_extra_medical_claim():
    from backend.ai_engine.v3.agent3 import build_tone_profile_v31, build_generation_spec_v31, build_five_tone_analysis_v31
    from tests.ai_engine.v3.test_agent3_v31 import _decision
    decision = _decision("spleen", "gong")
    profile = build_tone_profile_v31(diagnosis_id="diag_secondary", organ_weights={"spleen": 1},
        supporting_evidence_refs=["f1"], mapping=_mapping(), dominance_decision=decision, secondary_threshold=.1)
    spec = build_generation_spec_v31(profile=profile, parameter_rules=_rules(), secondary_threshold=.1)
    read = build_five_tone_analysis_v31(confirmed_user_state_ref={"confirmed_user_state_id": "cus_secondary", "revision": 1, "content_checksum": "sha256:x"},
        confirmed_state="已确认资料", state_tendency="缺少可公开引用的具体状态依据。", profile=profile,
        evidence_refs=["f1"], mapping=_mapping(), generation_spec=spec, dominance_decision=decision)
    assert read.secondary_tone.tone == profile.secondary_tone
    assert "辅音" in read.secondary_tone.explanation
    assert "既定五音对应关系" in read.secondary_tone.explanation
    assert "治疗" not in read.secondary_tone.explanation


def test_conflicting_excluded_facts_are_not_positive_explanation_refs():
    from backend.ai_engine.v3.public_explanation import public_facts
    from backend.app.schemas.v3.assessment import FactEvidence
    evidence, links = synthetic_evidence({"spleen": 1.8})
    evidence = [FactEvidence.model_validate({**item.model_dump(), "time_window": "source_recorded"}) for item in evidence]
    result = public_facts(evidence, links, excluded_ids=[evidence[0].fact_id])
    assert evidence[0].fact_evidence_id not in [item.evidence_id for item in result]
    assert evidence[1].fact_evidence_id in [item.evidence_id for item in result]

import pytest


def _mapping():
    return {
        "schema_id": "five-tone_mapping_v3",
        "schema_version": "3.0.0",
        "organ_tone_weights": {
            "primary": {
                "liver": {"jiao": 0.7, "shang": 0.15, "zhi": 0.15},
                "heart": {"zhi": 0.7, "gong": 0.15, "yu": 0.15},
                "spleen": {"gong": 0.7, "zhi": 0.15, "shang": 0.15},
                "lung": {"shang": 0.7, "gong": 0.15, "jiao": 0.15},
                "kidney": {"yu": 0.7, "gong": 0.15, "shang": 0.15},
            }
        },
        "organ_tone_table": [
            {"tone": "jiao", "tone_cn": "角调", "note": "舒展条达"},
            {"tone": "zhi", "tone_cn": "徵调", "note": "欢快升发"},
            {"tone": "gong", "tone_cn": "宫调", "note": "沉稳中和"},
            {"tone": "shang", "tone_cn": "商调", "note": "清越肃降"},
            {"tone": "yu", "tone_cn": "羽调", "note": "柔润静谧"},
        ],
    }


def test_agent3_builds_v31_tone_profile_deterministically_from_approved_mapping():
    from backend.ai_engine.v3.agent3 import build_tone_profile_v31

    profile = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 0.6, "spleen": 0.4},
        supporting_evidence_refs=["fact_1", "fact_2"],
        mapping=_mapping(),
    )

    assert profile.primary_tone.value == "zhi"
    assert profile.secondary_tone is None
    assert set(profile.weights) == {"jiao", "zhi", "gong", "shang", "yu"}
    assert abs(sum(profile.weights.values()) - 1.0) <= 0.001
    assert profile.basis.supporting_evidence_refs == ["fact_1", "fact_2"]


def test_agent3_accepts_the_repository_approved_five_tone_mapping_shape():
    from backend.app.services.v3.knowledge_assets import load_five_tone_mapping
    from backend.ai_engine.v3.agent3 import build_tone_profile_v31

    mapping = load_five_tone_mapping()
    profile = build_tone_profile_v31(
        diagnosis_id="diag_approved_mapping",
        organ_weights={"heart": 1.0},
        supporting_evidence_refs=["fact_approved"],
        mapping=mapping,
    )

    assert profile.mapping_version == "five_tone_mapping_v3@3.0.0"


def test_agent3_only_emits_secondary_tone_when_an_explicit_threshold_is_supplied():
    from backend.ai_engine.v3.agent3 import build_tone_profile_v31

    without_threshold = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 0.6, "spleen": 0.4},
        supporting_evidence_refs=["fact_1"],
        mapping=_mapping(),
    )
    with_threshold = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 0.6, "spleen": 0.4},
        supporting_evidence_refs=["fact_1"],
        mapping=_mapping(),
        secondary_threshold=0.1,
    )

    assert without_threshold.secondary_tone is None
    assert with_threshold.secondary_tone is not None
    assert with_threshold.secondary_tone != with_threshold.primary_tone


def test_agent3_abstained_diagnosis_cannot_produce_syndrome_tone_profile():
    from backend.ai_engine.v3.agent3 import Agent3Blocked, build_tone_profile_v31

    with pytest.raises(Agent3Blocked, match="DIAGNOSIS_NOT_AVAILABLE"):
        build_tone_profile_v31(
            diagnosis_id="diag_1",
            diagnosis_status="abstained",
            organ_weights={"heart": 1.0},
            supporting_evidence_refs=["fact_1"],
            mapping=_mapping(),
        )


def test_agent3_user_goal_is_not_part_of_medical_tone_calculation():
    from backend.ai_engine.v3.agent3 import build_tone_profile_v31

    first = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 1.0},
        supporting_evidence_refs=["fact_1"],
        mapping=_mapping(),
        user_goal={"primary_goal": "sleep"},
    )
    second = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 1.0},
        supporting_evidence_refs=["fact_1"],
        mapping=_mapping(),
        user_goal={"primary_goal": "energy"},
    )

    assert first.weights == second.weights
    assert first.primary_tone == second.primary_tone


def test_agent3_builds_public_read_model_without_internal_provider_fields():
    from backend.ai_engine.v3.agent3 import (
        build_five_tone_analysis_v31,
        build_tone_profile_v31,
    )

    profile = build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 0.6, "spleen": 0.4},
        supporting_evidence_refs=["fact_1", "fact_2"],
        mapping=_mapping(),
    )
    read_model = build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": "cus_1",
            "revision": 2,
            "content_checksum": "sha256:confirmed-state",
        },
        confirmed_state="最近一周睡眠恢复感一般。",
        state_tendency="整体偏向需要舒缓与稳定。",
        profile=profile,
        evidence_refs=["fact_1", "fact_2"],
        mapping=_mapping(),
        generation_parameters={
            "bpm": 60,
            "instruments": ["古琴"],
            "ambience": ["细雨"],
            "duration_seconds": 900,
        },
    )

    assert read_model.primary_tone.tone.value == "zhi"
    assert read_model.generation.status == "not_ready"
    dumped = str(read_model.model_dump(mode="json"))
    assert "provider" not in dumped.lower()
    assert "prompt" not in dumped.lower()
    assert "raw" not in dumped.lower()

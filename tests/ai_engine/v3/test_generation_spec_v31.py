import pytest


def _profile():
    from backend.ai_engine.v3.agent3 import build_tone_profile_v31

    return build_tone_profile_v31(
        diagnosis_id="diag_1",
        organ_weights={"heart": 1.0},
        supporting_evidence_refs=["fact_1"],
        mapping={
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
        },
    )


def _rules():
    return {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "owner-pending",
        "asset_version": "owner-approved-test-v1",
        "review_status": "approved",
        "secondary_goal_merge_policy": "primary_over_secondary_fill_missing",
        "default": {
            "bpm": 60,
            "instruments": ["古琴"],
            "ambience": ["细雨"],
            "duration_seconds": 180,
            "explanations": {
                "bpm": "按已批准的音乐参数规则提供参考速度。",
                "instruments": "按已批准的音乐参数规则提供配器参考。",
                "ambience": "按已批准的音乐参数规则提供环境参考。",
                "duration": "按已批准的音乐参数规则提供参考时长。",
            },
        },
        "goals": {
            "sleep": {
                "bpm": 50,
                "instruments": ["古琴", "箫"],
                "ambience": ["细雨"],
                "duration_seconds": 240,
                "explanations": {
                    "bpm": "助眠诉求对应的速度候选。",
                    "instruments": "助眠诉求对应的配器候选。",
                    "ambience": "助眠诉求对应的环境音候选。",
                    "duration": "助眠诉求对应的预计时长候选。",
                },
            },
            "relaxation": {},
            "emotion_regulation": {},
            "focus": {},
            "energy": {},
            "stress_relief": {},
            "other": {},
        },
    }


def test_generation_spec_is_deterministic_and_bounded_by_approved_rules():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=_rules(),
        user_goal={"primary_goal": "sleep"},
    )

    assert spec.primary_tone.value == "zhi"
    assert spec.secondary_tone is None
    assert spec.bpm == 50
    assert spec.instruments == ["古琴", "箫"]
    assert spec.duration_seconds == 240
    assert spec.secondary_tone_blocked is True
    assert spec.readiness == "ready"
    assert spec.blocking_reasons == []
    assert "user_goal" not in spec.model_dump(mode="json")


def test_generation_spec_without_approved_parameter_asset_is_explicitly_blocked():
    from backend.ai_engine.v3.agent3 import Agent3Blocked, build_generation_spec_v31

    with pytest.raises(Agent3Blocked, match="MUSIC_PARAMETER_ASSET_UNAVAILABLE"):
        build_generation_spec_v31(profile=_profile(), parameter_rules=None)


def test_generation_spec_does_not_allow_user_goal_to_change_medical_tone_profile():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31

    sleep_spec = build_generation_spec_v31(
        profile=_profile(), parameter_rules=_rules(), user_goal={"primary_goal": "sleep"}
    )
    default_spec = build_generation_spec_v31(profile=_profile(), parameter_rules=_rules())

    assert sleep_spec.primary_tone == default_spec.primary_tone
    assert sleep_spec.tone_weights == default_spec.tone_weights
    assert sleep_spec.bpm != default_spec.bpm


def test_generation_spec_custom_text_without_goal_code_falls_back_to_default_rules():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=_rules(),
        user_goal={
            "primary_goal": None,
            "secondary_goal": None,
            "custom_goal_text": "希望音乐更安静一些",
        },
    )

    assert spec.bpm == 60
    assert spec.instruments == ["古琴"]
    assert spec.ambience == ["细雨"]
    assert spec.duration_seconds == 180
    assert spec.readiness == "ready"
    assert spec.blocking_reasons == []

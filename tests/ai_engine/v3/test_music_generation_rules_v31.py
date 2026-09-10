import hashlib
import json

import pytest


def _payload():
    payload = {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "3.1.0",
        "asset_version": "owner-approved-test-v1",
        "review_status": "approved",
        "secondary_goal_merge_policy": "primary_over_secondary_fill_missing",
        "default": {
            "bpm": 60,
            "instruments": ["古琴"],
            "ambience": ["细雨"],
            "duration_seconds": 180,
            "explanations": {
                "bpm": "按批准规则提供速度参考。",
                "instruments": "按批准规则提供配器参考。",
                "ambience": "按批准规则提供环境参考。",
                "duration": "按批准规则提供时长参考。",
            },
        },
        "goals": {
            "sleep": {"bpm": 50, "instruments": ["古琴", "箫"], "ambience": ["细雨"], "duration_seconds": 240},
            "relaxation": {"bpm": 54, "instruments": ["古琴"], "ambience": ["溪流"], "duration_seconds": 240},
            "emotion_regulation": {"bpm": 60, "instruments": ["古琴", "琵琶"], "ambience": ["微风"], "duration_seconds": 180},
            "focus": {"bpm": 72, "instruments": ["箫"], "ambience": ["无额外环境音"], "duration_seconds": 180},
            "energy": {"bpm": 84, "instruments": ["笛"], "ambience": ["流水"], "duration_seconds": 180},
            "stress_relief": {"bpm": 56, "instruments": ["古琴", "埙"], "ambience": ["细雨"], "duration_seconds": 240},
            "other": {},
        },
        "content_checksum": "",
    }
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return payload


def _write_payload(tmp_path, payload):
    path = tmp_path / "music-generation-rules-v3.1.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_music_generation_rules_loader_validates_approved_schema_and_checksum(tmp_path):
    from backend.app.services.v3.knowledge_assets import load_music_generation_rules

    payload = _payload()
    asset = load_music_generation_rules(
        _write_payload(tmp_path, payload),
        expected_version=payload["asset_version"],
        expected_checksum=payload["content_checksum"],
    )

    assert asset["schema_id"] == "music_generation_rules_v3.1"
    assert asset["review_status"] == "approved"
    assert asset["content_checksum"] == payload["content_checksum"]
    assert set(asset["goals"]) == {
        "sleep", "relaxation", "emotion_regulation", "focus", "energy",
        "stress_relief", "other",
    }
    assert asset["secondary_goal_merge_policy"] == "primary_over_secondary_fill_missing"


def test_loaded_music_generation_rules_drive_deterministic_generation_spec(tmp_path):
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from backend.app.services.v3.knowledge_assets import load_music_generation_rules
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    payload = _payload()
    asset = load_music_generation_rules(
        _write_payload(tmp_path, payload),
        expected_version=payload["asset_version"],
        expected_checksum=payload["content_checksum"],
    )

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=asset,
        user_goal={"primary_goal": "sleep"},
    )

    assert spec.bpm == 50
    assert spec.duration_seconds == 240
    assert spec.readiness == "ready"


def test_loader_rejects_incomplete_goal_overrides(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    del payload["goals"]["focus"]
    payload = _rechecksum(payload)

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_INVALID"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=payload["content_checksum"],
        )


def test_loader_rejects_non_formal_goal_code(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    payload["goals"]["made_up_goal"] = payload["goals"].pop("other")
    payload = _rechecksum(payload)

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_INVALID"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=payload["content_checksum"],
        )


def test_loader_rejects_duration_over_300_seconds(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    payload["goals"]["sleep"]["duration_seconds"] = 301
    payload = _rechecksum(payload)

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_INVALID"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=payload["content_checksum"],
        )


def test_loader_rejects_missing_deterministic_parameter_explanations(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    del payload["default"]["explanations"]["duration"]
    payload = _rechecksum(payload)

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_INVALID"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=payload["content_checksum"],
        )


def test_generation_spec_rejects_incomplete_goal_rules_without_loader_bypass():
    from backend.ai_engine.v3.agent3 import Agent3Blocked, build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    payload = _payload()
    del payload["goals"]["focus"]

    with pytest.raises(Agent3Blocked, match="MUSIC_PARAMETER_ASSET_INVALID"):
        build_generation_spec_v31(
            profile=_profile(),
            parameter_rules=payload,
            user_goal={"primary_goal": "sleep"},
        )


def test_generation_spec_merges_secondary_goal_without_ignoring_it():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    payload = _payload()
    payload["goals"]["sleep"] = {"bpm": 50}

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=payload,
        user_goal={"primary_goal": "sleep", "secondary_goal": "energy"},
    )

    assert spec.bpm == 50
    assert spec.instruments == ["笛"]
    assert spec.ambience == ["流水"]
    assert spec.duration_seconds == 180


def test_primary_goal_wins_deterministically_when_both_goals_set_same_field():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=_payload(),
        user_goal={"primary_goal": "sleep", "secondary_goal": "energy"},
    )

    assert spec.bpm == 50
    assert spec.instruments == ["古琴", "箫"]
    assert spec.ambience == ["细雨"]
    assert spec.duration_seconds == 240


@pytest.mark.parametrize(
    "user_goal",
    [
        None,
        {},
        {"primary_goal": "other", "custom_goal_text": "希望更安静"},
        {"custom_goal_text": "希望更安静"},
    ],
)
def test_other_custom_only_and_skip_safely_use_default_rules(user_goal):
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=_payload(),
        user_goal=user_goal,
    )

    assert spec.bpm == 60
    assert spec.instruments == ["古琴"]
    assert spec.ambience == ["细雨"]
    assert spec.duration_seconds == 180


def _rechecksum(payload):
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return payload


def test_music_generation_rules_loader_rejects_the_safe_expression_asset(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    payload["schema_id"] = "five-tone-safe-expression-rules-v3.1"
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_SCHEMA_INVALID"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=payload["content_checksum"],
        )


def test_music_generation_rules_loader_rejects_checksum_tampering(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    payload["default"]["bpm"] = 61

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_CHECKSUM_MISMATCH"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=_payload()["content_checksum"],
        )


def test_music_generation_rules_loader_rejects_invalid_parameter_schema(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    payload["default"]["bpm"] = 121
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    with pytest.raises(MusicGenerationRuleAssetNotReady, match="MUSIC_PARAMETER_ASSET_INVALID"):
        load_music_generation_rules(
            _write_payload(tmp_path, payload),
            expected_version=payload["asset_version"],
            expected_checksum=payload["content_checksum"],
        )

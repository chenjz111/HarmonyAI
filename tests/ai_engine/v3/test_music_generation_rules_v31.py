import hashlib
import json
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
APPROVED_ASSET_PATH = REPOSITORY_ROOT / "knowledge" / "v3" / "music-generation-rules-v3.1.json"
APPROVED_ASSET_VERSION = "music-generation-rules-v3.1-r1"
APPROVED_ASSET_CHECKSUM = "sha256:b8b65b2658ea849945a43884bb786d59689606e4cdb97d63620df8b5179539be"


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
                "duration": "按批准规则提供预计时长参考。",
            },
        },
        "goals": {
            "sleep": {
                "bpm": 50,
                "duration_seconds": 240,
                "explanations": {
                    "bpm": "主要目标对应的速度候选。",
                    "duration": "主要目标对应的预计时长候选。",
                },
            },
            "relaxation": {
                "ambience": ["溪流"],
                "duration_seconds": 240,
                "explanations": {
                    "ambience": "次要目标对应的环境音候选。",
                    "duration": "次要目标对应的预计时长候选。",
                },
            },
            "emotion_regulation": {
                "instruments": ["古琴", "琵琶"],
                "ambience": ["微风"],
                "explanations": {
                    "instruments": "目标对应的乐器候选。",
                    "ambience": "目标对应的环境音候选。",
                },
            },
            "focus": {
                "bpm": 72,
                "ambience": ["无额外环境音"],
                "explanations": {
                    "bpm": "目标对应的速度候选。",
                    "ambience": "目标对应的环境音候选。",
                },
            },
            "energy": {
                "bpm": 84,
                "instruments": ["笛"],
                "explanations": {
                    "bpm": "目标对应的速度候选。",
                    "instruments": "目标对应的乐器候选。",
                },
            },
            "stress_relief": {
                "instruments": ["古琴", "埙"],
                "duration_seconds": 240,
                "explanations": {
                    "instruments": "目标对应的乐器候选。",
                    "duration": "目标对应的预计时长候选。",
                },
            },
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


def test_repository_approved_music_rules_are_versioned_and_checksum_bound():
    from backend.app.services.v3.knowledge_assets import load_music_generation_rules

    asset = load_music_generation_rules(
        APPROVED_ASSET_PATH,
        expected_version=APPROVED_ASSET_VERSION,
        expected_checksum=APPROVED_ASSET_CHECKSUM,
    )

    assert asset["asset_version"] == APPROVED_ASSET_VERSION
    assert asset["content_checksum"] == APPROVED_ASSET_CHECKSUM
    assert asset["default"] == _payload()["default"]
    assert asset["goals"] == _payload()["goals"]
    assert "预计时长" in asset["default"]["explanations"]["duration"]


def test_agent3_asset_loader_requires_version_and_checksum(monkeypatch):
    from backend.app.services.v3 import internal_agent3_service

    monkeypatch.setenv("V31_MUSIC_GENERATION_RULES_PATH", str(APPROVED_ASSET_PATH))
    monkeypatch.delenv("V31_MUSIC_GENERATION_RULES_VERSION", raising=False)
    monkeypatch.delenv("V31_MUSIC_GENERATION_RULES_CHECKSUM", raising=False)

    with pytest.raises(
        internal_agent3_service.Agent3NotReady,
        match="音乐参数规则资产版本或校验和尚未配置",
    ) as error:
        internal_agent3_service.load_agent3_assets()

    assert error.value.code == "MUSIC_PARAMETER_ASSET_NOT_CONFIGURED"


def test_agent3_asset_loader_uses_repository_approved_rules(monkeypatch):
    from backend.app.services.v3 import internal_agent3_service

    monkeypatch.setenv("V31_MUSIC_GENERATION_RULES_PATH", str(APPROVED_ASSET_PATH))
    monkeypatch.setenv("V31_MUSIC_GENERATION_RULES_VERSION", APPROVED_ASSET_VERSION)
    monkeypatch.setenv("V31_MUSIC_GENERATION_RULES_CHECKSUM", APPROVED_ASSET_CHECKSUM)

    mapping, rules = internal_agent3_service.load_agent3_assets()

    assert mapping["schema_id"] == "five_tone_mapping_v3"
    assert rules["asset_version"] == APPROVED_ASSET_VERSION
    assert rules["content_checksum"] == APPROVED_ASSET_CHECKSUM


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
    assert spec.explanations["bpm"] == "主要目标对应的速度候选。"
    assert spec.explanations["instruments"] == "按批准规则提供配器参考。"
    assert spec.explanations["ambience"] == "按批准规则提供环境参考。"
    assert spec.explanations["duration"] == "主要目标对应的预计时长候选。"
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


def test_loader_rejects_override_explanation_for_unoverridden_field(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MusicGenerationRuleAssetNotReady,
        load_music_generation_rules,
    )

    payload = _payload()
    payload["goals"]["focus"]["explanations"]["duration"] = "不应描述未覆盖的预计时长。"
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


@pytest.mark.parametrize(
    ("goal_code", "expected"),
    [
        ("sleep", (50, ["古琴"], ["细雨"], 240)),
        ("relaxation", (60, ["古琴"], ["溪流"], 240)),
        ("emotion_regulation", (60, ["古琴", "琵琶"], ["微风"], 180)),
        ("focus", (72, ["古琴"], ["无额外环境音"], 180)),
        ("energy", (84, ["笛"], ["细雨"], 180)),
        ("stress_relief", (60, ["古琴", "埙"], ["细雨"], 240)),
        ("other", (60, ["古琴"], ["细雨"], 180)),
    ],
)
def test_each_formal_goal_uses_only_its_partial_override(goal_code, expected):
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=_payload(),
        user_goal={"primary_goal": goal_code},
    )

    assert (spec.bpm, spec.instruments, spec.ambience, spec.duration_seconds) == expected


def test_generation_spec_merges_secondary_goal_without_ignoring_it():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    payload = _payload()
    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=payload,
        user_goal={"primary_goal": "sleep", "secondary_goal": "relaxation"},
    )

    assert spec.bpm == 50
    assert spec.instruments == ["古琴"]
    assert spec.ambience == ["溪流"]
    assert spec.duration_seconds == 240
    assert spec.explanations["bpm"] == "主要目标对应的速度候选。"
    assert spec.explanations["ambience"] == "次要目标对应的环境音候选。"
    assert spec.explanations["duration"] == "主要目标对应的预计时长候选。"


def test_primary_goal_wins_deterministically_when_both_goals_set_same_field():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=_payload(),
        user_goal={"primary_goal": "sleep", "secondary_goal": "energy"},
    )

    assert spec.bpm == 50
    assert spec.instruments == ["笛"]
    assert spec.ambience == ["细雨"]
    assert spec.duration_seconds == 240
    assert spec.explanations["bpm"] == "主要目标对应的速度候选。"
    assert spec.explanations["instruments"] == "目标对应的乐器候选。"
    assert spec.explanations["ambience"] == "按批准规则提供环境参考。"
    assert spec.explanations["duration"] == "主要目标对应的预计时长候选。"


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


def test_secondary_goal_equal_to_default_does_not_claim_application():
    from backend.ai_engine.v3.agent3 import build_generation_spec_v31
    from tests.ai_engine.v3.test_generation_spec_v31 import _profile

    payload = _payload()
    payload["goals"]["emotion_regulation"] = {
        "bpm": 60,
        "explanations": {"bpm": "次要目标对应的速度候选。"},
    }

    spec = build_generation_spec_v31(
        profile=_profile(),
        parameter_rules=payload,
        user_goal={"primary_goal": "other", "secondary_goal": "emotion_regulation"},
    )

    assert spec.bpm == 60
    assert spec.explanations["bpm"] == "按批准规则提供速度参考。"
    assert "次要目标" not in spec.explanations["bpm"]


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

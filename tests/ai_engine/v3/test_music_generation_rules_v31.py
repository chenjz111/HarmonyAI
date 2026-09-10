import hashlib
import json

import pytest


def _payload():
    payload = {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "3.1.0",
        "asset_version": "owner-approved-test-v1",
        "review_status": "approved",
        "default": {
            "bpm": 60,
            "instruments": ["古琴"],
            "ambience": ["细雨"],
            "duration_seconds": 900,
            "explanations": {
                "bpm": "按批准规则提供速度参考。",
                "instruments": "按批准规则提供配器参考。",
                "ambience": "按批准规则提供环境参考。",
                "duration": "按批准规则提供时长参考。",
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
    assert spec.duration_seconds == 1200
    assert spec.readiness == "ready"


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

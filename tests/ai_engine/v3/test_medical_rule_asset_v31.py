import hashlib
import json

import pytest


FORMAL_CODES = [f"syd_{index:03d}" for index in range(1, 9)]
FORMAL_ALIASES = {
    "syd_001": "liver_stagnation_heat",
    "syd_002": "liver_qi_stagnation",
    "syd_003": "heart_fire_flare",
    "syd_004": "heart_spleen_deficiency",
    "syd_005": "spleen_deficiency_dampness",
    "syd_006": "lung_qi_deficiency",
    "syd_007": "kidney_yin_deficiency",
    "syd_008": "heart_kidney_discordance",
}


def _write_rule_asset(tmp_path, *, version="medical-rules-v3.1-r1", codes=None):
    payload = {
        "schema_id": "medical_rules_v3.1",
        "schema_version": "3.1.0",
        "medical_rule_version": version,
        "review_status": "approved",
        "allowed_syndrome_codes": codes or FORMAL_CODES,
        "syndrome_aliases": FORMAL_ALIASES,
        "content_checksum": "",
    }
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "medical-rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def test_medical_rule_asset_loads_codes_only_from_approved_checked_asset(tmp_path):
    from backend.app.services.v3.knowledge_assets import load_medical_rule_asset

    path, payload = _write_rule_asset(tmp_path)
    asset = load_medical_rule_asset(
        path,
        expected_version="medical-rules-v3.1-r1",
        expected_checksum=payload["content_checksum"],
    )

    assert asset.medical_rule_version == "medical-rules-v3.1-r1"
    assert asset.allowed_syndrome_codes == frozenset(FORMAL_CODES)
    assert dict(asset.syndrome_aliases) == FORMAL_ALIASES


def test_formal_medical_rule_asset_matches_owner_whitelist_and_checksum():
    from backend.app.services.v3.knowledge_assets import _canonical_asset_checksum

    path = __import__("pathlib").Path(__file__).resolve().parents[3] / "knowledge" / "v3" / "medical-rules-v3.1.json"
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))

    assert payload["medical_rule_version"] == "medical-rules-v3.1-r1"
    assert payload["allowed_syndrome_codes"] == FORMAL_CODES
    assert set(payload["syndrome_aliases"]) == set(FORMAL_CODES)
    assert set(payload["syndrome_aliases"].values()) == set(FORMAL_ALIASES.values())
    assert payload["allowed_syndrome_codes"] != list(payload["syndrome_aliases"].values())
    assert payload["content_checksum"] == _canonical_asset_checksum(payload)


def test_formal_medical_rule_asset_loads_through_authoritative_loader():
    from pathlib import Path

    from backend.app.services.v3.knowledge_assets import load_medical_rule_asset

    path = Path(__file__).resolve().parents[3] / "knowledge" / "v3" / "medical-rules-v3.1.json"
    asset = load_medical_rule_asset(
        path,
        expected_version="medical-rules-v3.1-r1",
        expected_checksum="sha256:0dd929cb7d2b7b8a11c9c1ad0fb5e4adb8f4807123263af7e2a7c1767b401a3f",
    )

    assert asset.allowed_syndrome_codes == frozenset(FORMAL_CODES)
    assert dict(asset.syndrome_aliases) == FORMAL_ALIASES


def test_medical_rule_asset_rejects_semantic_alias_as_primary_code(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MedicalRuleAssetNotReady,
        load_medical_rule_asset,
    )

    path, payload = _write_rule_asset(tmp_path, codes=["liver_stagnation_heat"])
    with pytest.raises(MedicalRuleAssetNotReady, match="MEDICAL_RULE_CODES_NOT_APPROVED"):
        load_medical_rule_asset(
            path,
            expected_version="medical-rules-v3.1-r1",
            expected_checksum=payload["content_checksum"],
        )


def test_medical_rule_asset_rejects_unapproved_release_version(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MedicalRuleAssetNotReady,
        load_medical_rule_asset,
    )

    path, payload = _write_rule_asset(tmp_path, version="medical-rules-v3.1-r2")
    with pytest.raises(MedicalRuleAssetNotReady, match="MEDICAL_RULE_VERSION_NOT_APPROVED"):
        load_medical_rule_asset(
            path,
            expected_version="medical-rules-v3.1-r2",
            expected_checksum=payload["content_checksum"],
        )


def test_medical_rule_asset_rejects_recalculated_but_unapproved_checksum(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MedicalRuleAssetNotReady,
        load_medical_rule_asset,
    )

    path, payload = _write_rule_asset(tmp_path)
    payload["release_note"] = "unapproved change"
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(MedicalRuleAssetNotReady, match="MEDICAL_RULE_CHECKSUM_NOT_APPROVED"):
        load_medical_rule_asset(
            path,
            expected_version="medical-rules-v3.1-r1",
            expected_checksum=payload["content_checksum"],
        )


def test_medical_rule_asset_rejects_checksum_mismatch(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MedicalRuleAssetNotReady,
        load_medical_rule_asset,
    )

    path, _payload = _write_rule_asset(tmp_path)
    with pytest.raises(MedicalRuleAssetNotReady, match="MEDICAL_RULE_ASSET_CHECKSUM_MISMATCH"):
        load_medical_rule_asset(
            path,
            expected_version="medical-rules-v3.1-r1",
            expected_checksum="sha256:tampered",
        )


def test_medical_rule_asset_rejects_version_mismatch(tmp_path):
    from backend.app.services.v3.knowledge_assets import (
        MedicalRuleAssetNotReady,
        load_medical_rule_asset,
    )

    path, payload = _write_rule_asset(tmp_path)
    with pytest.raises(MedicalRuleAssetNotReady, match="MEDICAL_RULE_VERSION_MISMATCH"):
        load_medical_rule_asset(
            path,
            expected_version="medical-rules-v3.1-r0",
            expected_checksum=payload["content_checksum"],
        )


def test_pipeline_factory_rejects_environment_defined_syndrome_codes(tmp_path):
    from backend.app.core.agent_config import (
        V31ReadinessFailure,
        get_v31_ai_pipeline_dependencies,
    )

    path, payload = _write_rule_asset(tmp_path)
    with pytest.raises(V31ReadinessFailure, match="MEDICAL_RULE_CODES_NOT_APPROVED"):
        get_v31_ai_pipeline_dependencies(
            {
                "HARMONYAI_REAL_AGENTS": "true",
                "DASHSCOPE_API_KEY": "configured-value",
                "DASHSCOPE_WORKSPACE_ID": "workspace-test",
                "QWEN_MODEL": "qwen-approved",
                "CHROMA_PERSIST_DIRECTORY": "data/chroma",
                "CHROMA_COLLECTION": "harmony_v31",
                "V31_MEDICAL_RULE_ASSET_PATH": str(path),
                "V31_MEDICAL_RULE_ASSET_CHECKSUM": payload["content_checksum"],
                "V31_MEDICAL_RULE_VERSION": "medical-rules-v3.1-r1",
                "V31_ALLOWED_SYNDROME_CODES": "invented_code",
                "V31_MUSIC_GENERATION_RULES_PATH": str(path),
            }
        )

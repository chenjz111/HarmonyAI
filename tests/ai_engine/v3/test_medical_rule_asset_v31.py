import hashlib
import json

import pytest


def _write_rule_asset(tmp_path, *, version="medical-rules-v3.1-r1", codes=None):
    payload = {
        "schema_id": "medical_rules_v3.1",
        "schema_version": "3.1.0",
        "medical_rule_version": version,
        "review_status": "approved",
        "allowed_syndrome_codes": codes or ["syndrome_1", "syndrome_2"],
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
    assert asset.allowed_syndrome_codes == frozenset({"syndrome_1", "syndrome_2"})


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

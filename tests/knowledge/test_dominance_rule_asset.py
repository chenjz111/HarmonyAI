"""Sprint 6 Phase 1B gate A — dominance rule asset identity and readiness.

The dominance rule asset is the single frozen source of the Phase 1B numbers.
These tests pin its identity, its canonical checksum, the frozen values, the
absence of forbidden gates, and the fail-closed loader behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.v3.knowledge_assets import (
    APPROVED_DOMINANCE_RULE_CHECKSUM,
    DOMINANCE_EVIDENCE_DENOMINATOR,
    DOMINANCE_MARGIN_THRESHOLD,
    DOMINANCE_MINIMUM_COVERAGE,
    DOMINANCE_NORMALIZED_PRECISION,
    DOMINANCE_RAW_RATIO_THRESHOLD,
    DOMINANCE_REASON_CODES,
    DOMINANCE_RULE_ASSET_VERSION,
    DOMINANCE_RULE_SCHEMA_ID,
    DominanceRuleAssetNotReady,
    canonical_asset_checksum,
    load_dominance_rule_asset,
    load_five_tone_mapping,
    load_organ_mapping,
)

ROOT = Path(__file__).resolve().parents[2]
ASSET_PATH = ROOT / "knowledge" / "v3" / "dominance-rule-v1.json"


def _asset() -> dict:
    return json.loads(ASSET_PATH.read_text(encoding="utf-8"))


def _load(**overrides) -> dict:
    kwargs = {
        "expected_version": DOMINANCE_RULE_ASSET_VERSION,
        "expected_checksum": APPROVED_DOMINANCE_RULE_CHECKSUM,
    }
    kwargs.update(overrides)
    return load_dominance_rule_asset(ASSET_PATH, **kwargs)


def test_asset_identity_and_approval():
    asset = _asset()
    assert asset["schema_id"] == DOMINANCE_RULE_SCHEMA_ID == "dominance_rule_contract"
    assert asset["schema_version"] == "1.0"
    assert asset["asset_version"] == "dominance-rule-v1.0-r1"
    assert asset["review_status"] == "approved"
    assert asset["medical_review"]["status"] == "approved"
    assert asset["medical_review"]["review_version"]
    assert asset["owner_approval"]["status"] == "approved"
    assert asset["owner_approval"]["approval_version"]


def test_embedded_checksum_matches_canonical_and_configured_release():
    asset = _asset()
    actual = canonical_asset_checksum(asset)
    assert asset["content_checksum"] == actual
    assert actual == APPROVED_DOMINANCE_RULE_CHECKSUM


def test_frozen_numbers_are_exact_and_inclusive():
    asset = _asset()
    evidence = asset["evidence_gate"]
    assert evidence["denominator"] == DOMINANCE_EVIDENCE_DENOMINATOR == 8
    assert evidence["minimum_coverage"] == DOMINANCE_MINIMUM_COVERAGE == 0.50
    assert evidence["comparison"] == ">="
    assert evidence["coverage_formula_version"]
    assert set(evidence["counted_directions"]) == {"supporting", "contradicting"}
    gate = asset["dominance_gate"]
    assert gate["normalized_precision"] == DOMINANCE_NORMALIZED_PRECISION == 4
    assert gate["normalized_margin_threshold"] == DOMINANCE_MARGIN_THRESHOLD == 0.08
    assert gate["normalized_margin_comparison"] == ">="
    assert gate["raw_ratio_threshold"] == DOMINANCE_RAW_RATIO_THRESHOLD == 1.20
    assert gate["raw_ratio_comparison"] == ">="
    assert gate["comparison_population"] == "legal_candidates_only"
    assert gate["top_ordering_authority"] == "canonical_raw_support"
    assert gate["exact_tie_basis"] == "canonical_raw_support_equality"


def test_forbidden_gates_are_absent():
    gate = _asset()["dominance_gate"]
    # Explicit nulls: the frozen phase declares these gates as *not* present
    # (no top1 hard gate, no epsilon, no entropy/spread gate).
    assert gate["top1_hard_gate"] is None
    assert gate["epsilon"] is None
    assert gate["entropy_or_spread_gate"] is None
    text = json.dumps(_asset(), ensure_ascii=False)
    assert "0.35" not in text  # no top1 >= 0.35 hard gate
    assert "spread_threshold" not in text


def test_legal_candidate_gate_defers_to_the_approved_organ_mapping():
    gate = _asset()["legal_candidate_gate"]
    assert gate["authority"] == "approved_organ_mapping"
    assert gate["minimum_effective_evidence_count"] == 2
    assert gate["minimum_raw_support"] == 0.75
    assert gate["comparison"] == ">="
    organ_mapping = load_organ_mapping()
    assert organ_mapping["thresholds"]["minimum_evidence_count"] == 2
    assert organ_mapping["thresholds"]["minimum_total_support"] == 0.75


def test_reason_vocabulary_and_precedence_are_complete():
    asset = _asset()
    assert set(asset["reason_codes"]) == set(DOMINANCE_REASON_CODES)
    assert len(DOMINANCE_REASON_CODES) == 11
    assert asset["reason_precedence"]["two_or_more_legal_candidates"] == [
        "INTEGRATED_EXACT_TOP_TIE",
        "INTEGRATED_DOMINANCE_CONFLICT",
        "INTEGRATED_MARGIN_BELOW_THRESHOLD",
        "INTEGRATED_RATIO_BELOW_THRESHOLD",
    ]
    upstream = {
        item["upstream_reason_code"]: item["reason_code"]
        for item in asset["evidence_gate"]["upstream_abstain_mappings"]
    }
    assert upstream == {
        "ELEMENT_EVIDENCE_INSUFFICIENT": "BASIC_ELEMENT_EVIDENCE_INSUFFICIENT",
        "RAG_EMPTY": "BASIC_RAG_EMPTY",
    }
    assert asset["failure_policy"]["technical_failures_are_not_modes"] is True
    assert asset["failure_policy"]["silent_mock_fallback"] is False
    assert asset["failure_policy"]["mapping_identity_mismatch"] == "readiness_failure"


def test_mapping_references_match_the_approved_assets():
    references = _asset()["references"]
    organ_mapping = load_organ_mapping()
    five_tone = load_five_tone_mapping()
    assert references["organ_mapping"] == {
        "schema_id": organ_mapping["schema_id"],
        "schema_version": organ_mapping["schema_version"],
        "content_checksum": organ_mapping["content_checksum"],
    }
    assert references["five_tone_mapping"] == {
        "schema_id": five_tone["schema_id"],
        "schema_version": five_tone["schema_version"],
        "content_checksum": five_tone["content_checksum"],
    }


def test_loader_returns_the_validated_asset():
    asset = _load()
    assert asset["schema_id"] == DOMINANCE_RULE_SCHEMA_ID
    assert asset["asset_version"] == DOMINANCE_RULE_ASSET_VERSION
    assert asset["evidence_gate"]["denominator"] == 8
    assert asset["decision_snapshot_schema_id"] == "organ_dominance_decision_v1"
    assert asset["read_model_schema_version"] == "five_tone_analysis_read_model_v3.3"


def test_loader_fails_closed_on_unconfigured_version_or_checksum():
    with pytest.raises(DominanceRuleAssetNotReady) as unset:
        load_dominance_rule_asset(
            ASSET_PATH, expected_version="", expected_checksum=""
        )
    assert unset.value.error_code == "DOMINANCE_RULE_ASSET_NOT_CONFIGURED"

    with pytest.raises(DominanceRuleAssetNotReady) as mismatch:
        _load(expected_checksum="sha256:" + "0" * 64)
    assert mismatch.value.error_code == "DOMINANCE_RULE_ASSET_CHECKSUM_MISMATCH"

    with pytest.raises(DominanceRuleAssetNotReady) as version:
        _load(expected_version="dominance-rule-v9.9-r9")
    assert version.value.error_code == "DOMINANCE_RULE_ASSET_VERSION_MISMATCH"


def test_loader_rejects_tampering_and_unapproved_assets(tmp_path):
    tampered = _asset()
    tampered["dominance_gate"]["normalized_margin_threshold"] = 0.05
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    assert canonical_asset_checksum(tampered) != APPROVED_DOMINANCE_RULE_CHECKSUM
    with pytest.raises(DominanceRuleAssetNotReady) as error:
        load_dominance_rule_asset(
            path,
            expected_version=DOMINANCE_RULE_ASSET_VERSION,
            expected_checksum=APPROVED_DOMINANCE_RULE_CHECKSUM,
        )
    assert error.value.error_code == "DOMINANCE_RULE_ASSET_CHECKSUM_MISMATCH"

    unapproved = _asset()
    unapproved["review_status"] = "candidate"
    unapproved.pop("content_checksum")
    unapproved["content_checksum"] = canonical_asset_checksum(unapproved)
    path = tmp_path / "unapproved.json"
    path.write_text(json.dumps(unapproved, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(DominanceRuleAssetNotReady) as error:
        load_dominance_rule_asset(
            path,
            expected_version=DOMINANCE_RULE_ASSET_VERSION,
            expected_checksum=unapproved["content_checksum"],
        )
    assert error.value.error_code == "DOMINANCE_RULE_ASSET_NOT_APPROVED"


def test_loader_rejects_a_self_consistent_asset_with_drifted_frozen_numbers(tmp_path):
    drifted = _asset()
    drifted["evidence_gate"]["denominator"] = 10
    drifted.pop("content_checksum")
    drifted["content_checksum"] = canonical_asset_checksum(drifted)
    path = tmp_path / "drifted.json"
    path.write_text(json.dumps(drifted, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(DominanceRuleAssetNotReady) as error:
        load_dominance_rule_asset(
            path,
            expected_version=DOMINANCE_RULE_ASSET_VERSION,
            expected_checksum=drifted["content_checksum"],
        )
    assert error.value.error_code == "DOMINANCE_RULE_ASSET_INVALID"

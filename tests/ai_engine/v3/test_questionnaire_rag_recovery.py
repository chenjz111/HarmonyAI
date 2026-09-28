from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GOLD_PATH = ROOT / "knowledge/v3/questionnaire-rag-gold-profiles-v1.json"
SIMILARITY_PATH = ROOT / "tests/fixtures/questionnaire-rag-similarity-v1.json"
CORPUS_PATH = ROOT / "knowledge/v3/rag-corpus-chunks-v3.1-approved.json"
POLICY_PATH = ROOT / "knowledge/v3/rag-query-policy-v3.2-approved.json"
INGESTION_PATH = ROOT / "knowledge/v3/rag-ingestion-manifest-v3.1-approved.json"
CLAIMS_PATH = ROOT / "knowledge/v3/claim-dictionary-v3.0.json"
QUESTIONNAIRE_PATH = ROOT / "knowledge/v3/questionnaire-v3.0.1.json"
ORGAN_MAPPING_PATH = ROOT / "knowledge/v3/organ-mapping-v3.0.json"
REVIEW_PATH = ROOT / "docs/sprint6/questionnaire-rag-medical-review.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gold() -> dict:
    return _load(GOLD_PATH)


def _fixture() -> dict:
    return _load(SIMILARITY_PATH)


def _canonical_checksum(payload: dict, excluded_key: str) -> str:
    value = {key: item for key, item in payload.items() if key != excluded_key}
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def test_authority_snapshot_matches_approved_repository_assets():
    gold = _gold()
    policy = _load(POLICY_PATH)
    ingestion = _load(INGESTION_PATH)
    corpus = _load(CORPUS_PATH)
    questionnaire = _load(QUESTIONNAIRE_PATH)
    claims = _load(CLAIMS_PATH)
    organ_mapping = _load(ORGAN_MAPPING_PATH)
    authority = gold["authority_snapshot"]

    assert authority == {
        "query_policy_asset_version": policy["asset_version"],
        "query_policy_content_checksum": policy["content_checksum"],
        "query_builder_version": policy["query_builder_version"],
        "top_k": policy["top_k"],
        "distance_metric": policy["distance_metric"],
        "source_cosine_threshold": policy["source_cosine_threshold"],
        "minimum_score": policy["minimum_score"],
        "score_conversion": policy["score_conversion"],
        "embedding_model": ingestion["embedding_model"],
        "embedding_dimension": ingestion["embedding_dimension"],
        "embedding_version": ingestion["embedding_version"],
        "knowledge_version": ingestion["knowledge_version"],
        "ingestion_manifest_checksum": ingestion["manifest_checksum"],
        "corpus_content_checksum": ingestion["corpus_checksum"],
        "approved_chunk_count": corpus["chunk_count"],
        "questionnaire_schema_version": questionnaire["schema_version"],
        "questionnaire_content_checksum": questionnaire["content_checksum"],
        "claim_dictionary_schema_version": claims["schema_version"],
        "claim_dictionary_content_checksum": claims["content_checksum"],
        "organ_mapping_version": organ_mapping["mapping_version"],
        "organ_mapping_content_checksum": organ_mapping["content_checksum"],
    }


def test_coverage_classifies_every_claim_and_questionnaire_claim_exactly_once():
    gold = _gold()
    dictionary = _load(CLAIMS_PATH)
    questionnaire = _load(QUESTIONNAIRE_PATH)
    coverage = gold["claim_coverage"]
    by_code = {item["claim_code"]: item for item in coverage}
    dictionary_codes = {item["claim_code"] for item in dictionary["entries"]}
    questionnaire_codes = {
        option["claim_code"]
        for question in questionnaire["questions"]
        for option in question["options"]
        if option.get("claim_code")
    }

    assert len(by_code) == len(coverage) == 32
    assert set(by_code) == dictionary_codes
    assert {item["support_class"] for item in coverage} == {
        "DIRECT_SUPPORT",
        "BOUNDARY_SUPPORT",
        "UNSUPPORTED",
    }
    assert sum(item["support_class"] == "DIRECT_SUPPORT" for item in coverage) == 13
    assert sum(item["support_class"] == "BOUNDARY_SUPPORT" for item in coverage) == 10
    assert sum(item["support_class"] == "UNSUPPORTED" for item in coverage) == 9
    assert {item["claim_code"] for item in coverage if item["questionnaire_active"]} == questionnaire_codes
    q_items = [item for item in coverage if item["questionnaire_active"]]
    assert len(q_items) == 24
    assert sum(item["support_class"] == "DIRECT_SUPPORT" for item in q_items) == 12
    assert sum(item["support_class"] == "BOUNDARY_SUPPORT" for item in q_items) == 9
    assert sum(item["support_class"] == "UNSUPPORTED" for item in q_items) == 3
    for code in ("flank_discomfort", "postmeal_heaviness", "nocturia"):
        assert by_code[code]["support_class"] == "UNSUPPORTED"
        assert by_code[code]["supporting_chunk_ids"] == []


def test_support_references_are_approved_and_unsupported_claims_have_no_hits():
    gold = _gold()
    corpus = _load(CORPUS_PATH)
    approved = {
        item["chunk_id"]
        for item in corpus["chunks"]
        if item["review_status"] == "approved"
    }
    for item in gold["claim_coverage"]:
        refs = set(item["supporting_chunk_ids"]) | set(item["boundary_chunk_ids"])
        assert refs <= approved
        if item["support_class"] == "UNSUPPORTED":
            assert not item["supporting_chunk_ids"]
            assert not item["boundary_chunk_ids"]


def test_gold_profile_matrix_contains_required_positive_negative_and_mixed_cases():
    gold = _gold()
    profiles = gold["profiles"]
    ids = [item["profile_id"] for item in profiles]
    assert len(ids) == len(set(ids))
    assert all(item["synthetic"] is True for item in profiles)

    positive_domains = {
        domain
        for item in profiles
        if item["expected_result"] == "POSITIVE"
        for domain in item["expected_retrieval_domains"]
    }
    assert {"anger_liver", "appetite_digestion", "respiratory", "kidney"} <= positive_domains
    assert {item["source_gold_query_id"] for item in profiles if item.get("source_gold_query_id")} >= {
        "gq_14",
        "gq_15",
        "gq_17",
    }
    for item in profiles:
        if item["expected_result"] in {"EMPTY", "NO_ANSWER"}:
            assert item["expected_positive_chunk_ids"] == []

    mixed = next(item for item in profiles if item["profile_id"] == "qrag_mixed_10_claims")
    assert 9 <= len(mixed["active_claim_codes"]) <= 11
    assert mixed["baseline_expectation"] == "CURRENT_COMBINED_QUERY_MAY_DILUTE_TO_EMPTY"


def test_confirmed_state_profile_excludes_removed_fact_from_active_retrieval():
    profile = next(
        item
        for item in _gold()["profiles"]
        if item["profile_id"] == "qrag_confirmed_edit_removes_anger"
    )
    assert "anger_tendency" in profile["provenance_claim_codes"]
    assert "anger_tendency" in profile["removed_or_contradicted_claim_codes"]
    assert "anger_tendency" not in profile["active_claim_codes"]
    assert "anger_tendency" not in profile["expected_query_claim_codes"]
    assert profile["confirmed_state_is_authority"] is True


def test_proposed_groups_are_mapping_derived_and_do_not_activate_history():
    gold = _gold()
    groups = gold["proposed_focused_query_groups"]
    approved_mapping = {
        item["claim_code"]: item["organ"]
        for item in _load(ORGAN_MAPPING_PATH)["single_mappings"]
    }
    assert {item["group_id"] for item in groups} == {
        "focus_liver",
        "focus_heart",
        "focus_spleen",
        "focus_lung",
        "focus_kidney",
    }
    assert all(item["status"] == "APPROVED_OFFLINE_NOT_ACTIVE" for item in groups)
    assert all(item["activation_rule"] == "ACTIVE_CONFIRMED_CLAIMS_ONLY" for item in groups)
    mapped = [code for item in groups for code in item["included_claim_codes"]]
    questionnaire_codes = {
        item["claim_code"]
        for item in gold["claim_coverage"]
        if item["questionnaire_active"]
    }
    assert len(mapped) == len(set(mapped)) + 1
    assert {code for code in mapped if mapped.count(code) > 1} == {"exertional_breathlessness"}
    assert set(mapped) == questionnaire_codes
    for group in groups:
        assert all(
            approved_mapping[code] == group["organ_code"]
            or (code == "exertional_breathlessness" and group["organ_code"] == "kidney")
            for code in group["included_claim_codes"]
        )


def test_similarity_fixture_is_offline_provenanced_and_checksum_valid():
    fixture = _fixture()
    gold = _gold()
    authority = gold["authority_snapshot"]
    assert fixture["provenance"]["mode"] == "SYNTHETIC_OFFLINE_NOT_LIVE_MEASUREMENT"
    assert fixture["provenance"]["real_embedding_calls"] == 0
    assert fixture["provenance"]["query_policy_version"] == authority["query_policy_asset_version"]
    assert fixture["provenance"]["corpus_version"] == authority["knowledge_version"]
    assert fixture["provenance"]["embedding_model"] == authority["embedding_model"]
    assert fixture["provenance"]["embedding_dimension"] == authority["embedding_dimension"]
    assert fixture["provenance"]["manifest_checksum"] == authority["ingestion_manifest_checksum"]
    assert fixture["fixture_checksum"] == _canonical_checksum(fixture, "fixture_checksum")

    approved = {item["chunk_id"] for item in _load(CORPUS_PATH)["chunks"]}
    profile_ids = {item["profile_id"] for item in gold["profiles"]}
    assert {item["profile_id"] for item in fixture["profile_results"]} == profile_ids
    for result in fixture["profile_results"]:
        assert result["query_identity"]
        for candidate in result["candidates"]:
            assert candidate["chunk_id"] in approved
            assert isinstance(candidate["normalized_score"], (int, float))
            assert 0 <= candidate["normalized_score"] <= 1
            assert candidate["filter_reason"] in {"APPROVED", "BELOW_MINIMUM_SCORE"}
            expected = (
                "APPROVED"
                if candidate["normalized_score"] + 1e-6 >= authority["minimum_score"]
                else "BELOW_MINIMUM_SCORE"
            )
            assert candidate["filter_reason"] == expected

    by_profile = {item["profile_id"]: item for item in fixture["profile_results"]}
    for profile in gold["profiles"]:
        approved_candidates = [
            item
            for item in by_profile[profile["profile_id"]]["candidates"]
            if item["filter_reason"] == "APPROVED"
        ]
        if profile["expected_result"] in {"EMPTY", "NO_ANSWER"}:
            assert approved_candidates == []
    assert not [
        item
        for item in by_profile["qrag_mixed_10_claims"]["candidates"]
        if item["filter_reason"] == "APPROVED"
    ]


def test_pack_contains_no_real_user_material_or_active_runtime_asset():
    gold = _gold()
    fixture = _fixture()
    serialized = json.dumps([gold, fixture], ensure_ascii=False)
    assert gold["data_policy"]["contains_real_user_text"] is False
    assert gold["data_policy"]["runtime_active"] is False
    assert fixture["provenance"]["runtime_active"] is False
    for forbidden in ("真实姓名", "身份证号", "手机号", "门诊号"):
        assert forbidden not in serialized


def test_medical_review_document_contains_all_required_decision_sections():
    document = REVIEW_PATH.read_text(encoding="utf-8")
    required_headings = [
        "## 1. Current production authority snapshot",
        "## 2. Root-cause hypothesis",
        "## 3. Current corpus coverage matrix",
        "## 4. Gold profile matrix",
        "## 5. Baseline/current-query observations",
        "## 6. Proposed focused query groups",
        "## 7. Unsupported and boundary claims",
        "## 8. Proposed corpus additions",
        "## 9. Negative/no-answer safety matrix",
        "## 10. Threshold preservation",
        "## 11. Confirmed-state authority",
        "## 12. Expected G2 runtime design (preview only)",
        "## 13. Is G3 needed?",
        "## 14. Medical Review decision table",
        "## 15. Owner decision table",
    ]
    assert all(heading in document for heading in required_headings)
    assert document.count("PROPOSED — NOT APPROVED — NOT ACTIVE") >= 2
    assert "merge key:" in document
    assert "retain the highest valid score" in document
    assert "MR-06" in document


def test_mr06_breathlessness_is_boundary_in_both_approved_groups():
    gold = _gold()
    item = next(row for row in gold["claim_coverage"] if row["claim_code"] == "exertional_breathlessness")
    assert item["support_class"] == "BOUNDARY_SUPPORT"
    assert item["supporting_chunk_ids"] == []
    assert item["boundary_chunk_ids"] == ["v31_src_08_scope_001", "v31_src_12_scope_001"]
    assert item["organ_provenance"] == {"primary": "lung", "secondary": ["kidney"], "review_ref": "MR-06"}
    groups = [row["group_id"] for row in gold["proposed_focused_query_groups"] if item["claim_code"] in row["included_claim_codes"]]
    assert groups == ["focus_lung", "focus_kidney"]
    respiratory = next(row for row in gold["profiles"] if row["profile_id"] == "qrag_positive_respiratory")
    assert "v31_src_08_scope_001" not in respiratory["expected_positive_chunk_ids"]
    assert {"v31_src_08_scope_001", "v31_src_12_scope_001"} <= set(respiratory["allowed_boundary_chunk_ids"])
    assert _fixture()["medical_review"]["exertional_breathlessness"] == item["organ_provenance"] | {"support_class": "BOUNDARY_SUPPORT"}

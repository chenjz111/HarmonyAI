# -*- coding: utf-8 -*-
"""Medical rules v3.1 assets: RAG gold query set + syndrome whitelist note — structure & integrity tests."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "docs" / "sprint5" / "rag-gold-queries-medical-20260909.json"
WHITELIST_MD = ROOT / "docs" / "sprint5" / "medical-syndrome-whitelist-and-rag-threshold-20260909.md"
WHITELIST_JSON = ROOT / "knowledge" / "v3" / "agent2-syndrome-whitelist-v3.1.json"
MEDICAL_RULES = ROOT / "knowledge" / "v3" / "medical-rules-v3.1.json"
CORPUS = ROOT / "knowledge" / "v3" / "rag-corpus-chunks-v3.1-approved.json"
INGESTION_MANIFEST = ROOT / "knowledge" / "v3" / "rag-ingestion-manifest-v3.1-approved.json"
SOURCE_REGISTRY = ROOT / "knowledge" / "v3" / "rag-corpus-manifest-v3.1.json"
EXPECTED_CHUNKS = [f"v31_src_{i:02d}_scope_001" for i in range(1, 14)]
EXPECTED_CORPUS_CHECKSUM = "sha256:fbf2207de75b963d316fc4bc54cb3e8e6c91f475d7766d4b27adec237101961a"
EXPECTED_REGISTRY_CHECKSUM = "sha256:5096bf8509fea4641fef8ca4965245b04a253b1e0bd3910dd0a6b64bef9afb85"
EXPECTED_MANIFEST_CHECKSUM = "sha256:4ffef480fd66d38cd8f3cecc96ccce4e1135869cdccbbf7b2162cbf9139a8f76"
EXPECTED_MEDICAL_REVIEW_VERSION = "medical-review-20260909-r1"
REQUIRED_FIELDS = ["query_id", "query_text", "relevant_chunk_ids",
                   "irrelevant_chunk_ids", "boundary_chunk_ids", "medical_note"]


def _load_gold():
    return json.loads(GOLD.read_text(encoding="utf-8"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_checksum(payload):
    data = {key: value for key, value in payload.items() if key != "content_checksum"}
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def test_01_gold_json_parseable_and_fields():
    g = _load_gold()
    assert isinstance(g.get("queries"), list)
    for q in g["queries"]:
        for f in REQUIRED_FIELDS:
            assert f in q, (q.get("query_id"), f)
        assert isinstance(q["query_text"], str) and q["query_text"].strip()
        assert isinstance(q["medical_note"], str) and q["medical_note"].strip()


def test_02_exactly_17_queries_and_chunk_id_integrity():
    g = _load_gold()
    assert len(g["queries"]) == 17
    chunk_set = set(EXPECTED_CHUNKS)
    for q in g["queries"]:
        ids = set(q["relevant_chunk_ids"]) | set(q["irrelevant_chunk_ids"]) | set(q["boundary_chunk_ids"])
        assert ids <= chunk_set, q["query_id"]
        assert set(q["relevant_chunk_ids"]) & set(q["irrelevant_chunk_ids"]) == set()
        assert set(q["boundary_chunk_ids"]) & set(q["irrelevant_chunk_ids"]) == set()
        assert set(q["relevant_chunk_ids"]) & set(q["boundary_chunk_ids"]) == set()
        assert len(q["relevant_chunk_ids"]) + len(q["boundary_chunk_ids"]) + len(q["irrelevant_chunk_ids"]) > 0


def test_03_chunk_set_declared_and_source_map():
    g = _load_gold()
    assert g.get("chunk_id_set") == EXPECTED_CHUNKS
    m = g.get("chunk_id_map_source", {})
    assert len(m) == 13
    for i in range(1, 14):
        assert m[f"src_{i:02d}"] == f"v31_src_{i:02d}_scope_001"


def test_04_annotation_rule_explicit():
    g = _load_gold()
    rule = g.get("annotation_rule", "")
    assert "irrelevant" in rule and "relevant/boundary" in rule


def test_05_syndrome_code_authority():
    g = _load_gold()
    auth = g.get("syndrome_code_authority", {})
    formal_rules = _load(MEDICAL_RULES)
    formal_aliases = formal_rules["syndrome_aliases"]
    assert auth.get("primary_codes") == formal_rules["allowed_syndrome_codes"]
    assert auth.get("english_alias") == formal_aliases


def test_06_empty_claim_organ_semantics_declared():
    g = _load_gold()
    assert "有意留空" in g.get("empty_claim_organ_semantics", "")


def test_07_whitelist_md_present_and_mentions_primary_codes():
    text = WHITELIST_MD.read_text(encoding="utf-8")
    assert "syd_001" in text and "syd_008" in text
    assert re.search(r"主键\s*=\s*`?syd_001`?", text) or "syd_001`~`syd_008" in text
    for alias in _load(MEDICAL_RULES)["syndrome_aliases"].values():
        assert alias in text


def test_08_gold_pins_medically_reviewed_corpus_identity():
    g = _load_gold()
    identity = g["reviewed_corpus_identity"]
    corpus = _load(CORPUS)
    registry = _load(SOURCE_REGISTRY)
    manifest = _load(INGESTION_MANIFEST)
    assert identity["chunk_count"] == len(corpus["chunks"]) == 13
    assert corpus["content_checksum"] == _canonical_checksum(corpus)
    assert registry["content_checksum"] == _canonical_checksum(registry)
    assert identity["corpus_content_checksum"] == corpus["content_checksum"] == EXPECTED_CORPUS_CHECKSUM
    assert identity["source_registry_checksum"] == registry["content_checksum"] == EXPECTED_REGISTRY_CHECKSUM
    assert corpus["source_registry_checksum"] == registry["content_checksum"]
    assert identity["change_requires_medical_rereview"] is True
    # Approved 身份三方对账：语料 / ingestion manifest / gold 的版本与 checksum 必须一致
    assert corpus["review_status"] == "approved"
    assert corpus["medical_review_version"] == EXPECTED_MEDICAL_REVIEW_VERSION
    assert manifest["medical_review_version"] == EXPECTED_MEDICAL_REVIEW_VERSION
    assert identity["medical_review_version"] == EXPECTED_MEDICAL_REVIEW_VERSION
    assert manifest["corpus_checksum"] == corpus["content_checksum"] == EXPECTED_CORPUS_CHECKSUM
    assert manifest["manifest_checksum"] == EXPECTED_MANIFEST_CHECKSUM
    assert identity["ingestion_manifest_checksum"] == manifest["manifest_checksum"]
    assert manifest["source_registry_checksum"] == registry["content_checksum"]
    assert identity["corpus_path"] == "knowledge/v3/rag-corpus-chunks-v3.1-approved.json"


def test_08c_approved_corpus_ids_and_text_match_reviewed_version():
    """13 chunk 的 ID/顺序与 gold 声明一致；正文一致性由 approved content_checksum 覆盖。"""
    corpus = _load(CORPUS)
    g = _load_gold()
    ids = [chunk["chunk_id"] for chunk in corpus["chunks"]]
    assert ids == EXPECTED_CHUNKS == g["chunk_id_set"]
    assert corpus["chunk_count"] == len(ids) == 13
    assert all(str(chunk.get("text", "")).strip() for chunk in corpus["chunks"])
    assert all(chunk.get("claim_codes") == [] and chunk.get("organ_codes") == []
               for chunk in corpus["chunks"])


def test_08b_reviewed_gold_labels_match_medical_decision():
    queries = {query["query_id"]: query for query in _load_gold()["queries"]}
    assert queries["gq_06"]["relevant_chunk_ids"] == [
        "v31_src_01_scope_001",
        "v31_src_07_scope_001",
    ]
    assert queries["gq_06"]["boundary_chunk_ids"] == ["v31_src_10_scope_001"]
    assert queries["gq_12"]["relevant_chunk_ids"] == ["v31_src_09_scope_001"]
    assert queries["gq_12"]["boundary_chunk_ids"] == ["v31_src_12_scope_001"]


def test_09_machine_readable_whitelist_is_complete_and_approved():
    asset = json.loads(WHITELIST_JSON.read_text(encoding="utf-8"))
    formal_rules = _load(MEDICAL_RULES)
    formal_aliases = formal_rules["syndrome_aliases"]
    assert asset["schema_id"] == "agent2_syndrome_whitelist_v3_1"
    assert asset["review_status"] == "MEDICALLY_APPROVED"
    entries = asset["allowed_syndromes"]
    assert len(entries) == 8
    assert [entry["stable_code"] for entry in entries] == [
        f"syd_{i:03d}" for i in range(1, 9)
    ]
    assert len({entry["english_alias"] for entry in entries}) == 8
    for entry in entries:
        assert entry["english_alias"] == formal_aliases[entry["stable_code"]]
        assert entry["display_name"].endswith("倾向")
        assert entry["medical_meaning"].strip()
        assert entry["supported_evidence_scope"]
        assert entry["insufficient_evidence_action"] == "abstain"

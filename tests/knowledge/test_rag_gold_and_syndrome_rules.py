# -*- coding: utf-8 -*-
"""Medical rules v3.1 assets: RAG gold query set + syndrome whitelist note — structure & integrity tests."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "docs" / "sprint5" / "rag-gold-queries-medical-20260909.json"
WHITELIST_MD = ROOT / "docs" / "sprint5" / "medical-syndrome-whitelist-and-rag-threshold-20260909.md"
EXPECTED_CHUNKS = [f"v31_src_{i:02d}_scope_001" for i in range(1, 14)]
REQUIRED_FIELDS = ["query_id", "query_text", "relevant_chunk_ids",
                   "irrelevant_chunk_ids", "boundary_chunk_ids", "medical_note"]


def _load_gold():
    return json.loads(GOLD.read_text(encoding="utf-8"))


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
    assert auth.get("primary_codes") == ["syd_%03d" % i for i in range(1, 9)]
    alias = auth.get("english_alias", {})
    assert len(alias) == 8
    for i in range(1, 9):
        assert alias[f"syd_{i:03d}"]  # alias present, primary key stays syd_xxx


def test_06_empty_claim_organ_semantics_declared():
    g = _load_gold()
    assert "有意留空" in g.get("empty_claim_organ_semantics", "")


def test_07_whitelist_md_present_and_mentions_primary_codes():
    text = WHITELIST_MD.read_text(encoding="utf-8")
    assert "syd_001" in text and "syd_008" in text
    assert re.search(r"主键\s*=\s*`?syd_001`?", text) or "syd_001`~`syd_008" in text

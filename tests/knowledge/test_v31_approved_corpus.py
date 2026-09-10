"""Contract tests for the Owner-approved V3.1 RAG corpus package."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
KNOWLEDGE = ROOT / "knowledge" / "v3"
REGISTRY_PATH = KNOWLEDGE / "rag-corpus-manifest-v3.1.json"
CORPUS_PATH = KNOWLEDGE / "rag-corpus-chunks-v3.1-approved.json"
MANIFEST_PATH = KNOWLEDGE / "rag-ingestion-manifest-v3.1-approved.json"
REVIEW_VERSION = "medical-review-20260909-r1"
KNOWLEDGE_VERSION = "medical_v3.1-approved.1"
EMPTY_LABEL_SEMANTICS = (
    "claim_codes_and_organ_codes_intentionally_empty_by_medical_review"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _checksum(payload: dict, field: str) -> str:
    canonical = {key: value for key, value in payload.items() if key != field}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def test_approved_corpus_is_exact_pr114_scope_with_owner_review_metadata():
    registry = _load(REGISTRY_PATH)
    candidate = _load(KNOWLEDGE / "rag-corpus-chunks-v3.1-candidate.json")
    corpus = _load(CORPUS_PATH)

    assert corpus["review_status"] == "approved"
    assert corpus["medical_review_version"] == REVIEW_VERSION
    assert corpus["source_registry_checksum"] == registry["content_checksum"]
    assert [item["source_id"] for item in corpus["chunks"]] == [
        item["source_id"] for item in registry["sources"]
    ]
    assert len(corpus["chunks"]) == 13

    immutable_fields = (
        "chunk_id",
        "source_id",
        "source_title",
        "source_reference",
        "source_content_hash",
        "section",
        "text",
        "display_summary",
        "claim_codes",
        "organ_codes",
    )
    for original, approved in zip(candidate["chunks"], corpus["chunks"], strict=True):
        assert {field: approved[field] for field in immutable_fields} == {
            field: original[field] for field in immutable_fields
        }
        assert approved["review_status"] == "approved"
        assert approved["medical_review_version"] == REVIEW_VERSION
        assert approved["knowledge_version"] == KNOWLEDGE_VERSION
        assert approved["content_checksum"] == _checksum(
            approved, "content_checksum"
        )


def test_approved_manifest_records_both_score_spaces_and_all_checksums():
    registry = _load(REGISTRY_PATH)
    corpus = _load(CORPUS_PATH)
    manifest = _load(MANIFEST_PATH)

    assert corpus["content_checksum"] == _checksum(corpus, "content_checksum")
    assert manifest["manifest_checksum"] == _checksum(manifest, "manifest_checksum")
    assert manifest["source_registry_checksum"] == registry["content_checksum"]
    assert manifest["corpus_checksum"] == corpus["content_checksum"]
    assert manifest["medical_review_version"] == REVIEW_VERSION
    assert manifest["knowledge_version"] == KNOWLEDGE_VERSION
    assert manifest["embedding_model"] == "text-embedding-v4"
    assert manifest["embedding_dimension"] == 1024
    assert manifest["embedding_version"] == "text-embedding-v4@1024"
    assert manifest["retrieval_score_semantics"] == "normalized_similarity"
    assert manifest["source_cosine_threshold"] == 0.65
    assert manifest["minimum_score"] == 0.740741
    assert manifest["score_conversion"] == (
        "normalized_similarity = 1 / (2 - cosine)"
    )
    assert manifest["label_semantics"] == EMPTY_LABEL_SEMANTICS
    assert manifest["chunk_count"] == 13
    assert manifest["chunk_checksums"] == [
        {
            "chunk_id": chunk["chunk_id"],
            "content_checksum": chunk["content_checksum"],
        }
        for chunk in corpus["chunks"]
    ]


def test_approved_corpus_passes_production_loader():
    from backend.ai_engine.v3.rag_ingestion import load_production_corpus

    manifest, chunks = load_production_corpus(MANIFEST_PATH, CORPUS_PATH)

    assert manifest.knowledge_version == KNOWLEDGE_VERSION
    assert manifest.minimum_score == 0.740741
    assert len(chunks) == 13
    assert {chunk.medical_review_version for chunk in chunks} == {REVIEW_VERSION}
    assert [chunk.source_id for chunk in chunks] == [
        f"src_{index:02d}" for index in range(1, 14)
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_cosine_threshold", 0.60),
        ("minimum_score", 0.65),
        ("score_conversion", "normalized_similarity = 1 / (1 + distance)"),
    ],
)
def test_approved_manifest_rejects_inconsistent_score_metadata(field, value):
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        validate_production_corpus,
    )

    manifest = _load(MANIFEST_PATH)
    corpus = _load(CORPUS_PATH)
    manifest[field] = value
    manifest["manifest_checksum"] = _checksum(manifest, "manifest_checksum")

    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_SCORE_METADATA_INVALID"):
        validate_production_corpus(manifest, corpus["chunks"], corpus_payload=corpus)


def test_approved_manifest_rejects_tampered_corpus_checksum():
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        load_production_corpus,
    )

    manifest = _load(MANIFEST_PATH)
    corpus = _load(CORPUS_PATH)
    tampered = copy.deepcopy(corpus)
    tampered["chunks"][0]["text"] = "tampered"
    tampered_path = CORPUS_PATH.with_name(".tmp-v31-approved-tampered.json")
    manifest_path = MANIFEST_PATH.with_name(".tmp-v31-approved-manifest.json")
    try:
        tampered_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ProductionCorpusNotReady, match="CORPUS_CHECKSUM_MISMATCH"):
            load_production_corpus(manifest_path, tampered_path)
    finally:
        tampered_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)

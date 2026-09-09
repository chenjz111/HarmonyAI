"""Contract tests for the PR #114-bound V3.1 candidate corpus package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
KNOWLEDGE = ROOT / "knowledge" / "v3"
REGISTRY_PATH = KNOWLEDGE / "rag-corpus-manifest-v3.1.json"
CANDIDATE_PATH = KNOWLEDGE / "rag-corpus-chunks-v3.1-candidate.json"
MANIFEST_PATH = KNOWLEDGE / "rag-ingestion-manifest-v3.1-candidate.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_checksum(payload: dict) -> str:
    data = {key: value for key, value in payload.items() if key != "content_checksum"}
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _chunk_checksum(chunk: dict) -> str:
    return _canonical_checksum(chunk)


def test_candidate_chunks_are_exactly_pr114_source_scope_rows():
    registry = _load(REGISTRY_PATH)
    candidate = _load(CANDIDATE_PATH)

    assert candidate["candidate_status"] == "PENDING_MEDICAL_CONTENT_REVIEW"
    assert candidate["source_registry_checksum"] == registry["content_checksum"]
    assert [row["source_id"] for row in candidate["chunks"]] == [
        row["source_id"] for row in registry["sources"]
    ]
    assert len(candidate["chunks"]) == 13

    for source, chunk in zip(registry["sources"], candidate["chunks"]):
        assert chunk["text"] == source["use"]
        assert chunk["display_summary"] == source["use"]
        assert chunk["source_title"] == source["title"]
        assert chunk["source_reference"] == source["source_reference"]
        assert chunk["source_content_hash"] == source["content_hash"]
        assert chunk["claim_codes"] == []
        assert chunk["organ_codes"] == []
        assert chunk["review_status"] == "pending_medical_review"
        assert chunk["source_registry_review_status"] == "medically_reviewed"
        assert chunk["content_checksum"] == _chunk_checksum(chunk)


def test_candidate_package_and_manifest_checksums_are_canonical():
    candidate = _load(CANDIDATE_PATH)
    manifest = _load(MANIFEST_PATH)

    assert candidate["content_checksum"] == _canonical_checksum(candidate)
    assert manifest["content_checksum"] == _canonical_checksum(manifest)
    assert manifest["candidate_status"] == "PENDING_MEDICAL_CONTENT_REVIEW"
    assert manifest["embedding_model"] == "text-embedding-v4"
    assert manifest["embedding_dimension"] == 1024
    assert manifest["embedding_version"] == "text-embedding-v4@1024"
    assert manifest["label_semantics"] == (
        "claim_codes_and_organ_codes_intentionally_empty_by_medical_review"
    )
    assert manifest["index_status"] == "NOT_BUILT_OWNER_PENDING"
    assert manifest["chunk_count"] == len(candidate["chunks"]) == 13
    assert manifest["chunk_checksums"] == [
        {
            "chunk_id": chunk["chunk_id"],
            "content_checksum": chunk["content_checksum"],
        }
        for chunk in candidate["chunks"]
    ]
    assert manifest["candidate_corpus_checksum"] == candidate["content_checksum"]


def test_candidate_contains_no_inferred_medical_labels_or_production_approval():
    candidate = _load(CANDIDATE_PATH)

    assert candidate["candidate_status"] != "PRODUCTION_APPROVED"
    for chunk in candidate["chunks"]:
        assert chunk["claim_codes"] == []
        assert chunk["organ_codes"] == []
        assert "medical_review_version" not in chunk
        assert "approved" not in chunk["review_status"]

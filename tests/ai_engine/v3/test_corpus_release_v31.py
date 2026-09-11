"""Tests for the V3.1 candidate-corpus promotion boundary."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
KNOWLEDGE = ROOT / "knowledge" / "v3"
REGISTRY_PATH = KNOWLEDGE / "rag-corpus-manifest-v3.1.json"
CANDIDATE_PATH = KNOWLEDGE / "rag-corpus-chunks-v3.1-candidate.json"
CANDIDATE_MANIFEST_PATH = KNOWLEDGE / "rag-ingestion-manifest-v3.1-candidate.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _checksum(payload: dict) -> str:
    data = {key: value for key, value in payload.items() if key != "content_checksum"}
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def test_candidate_loader_binds_all_chunks_to_pr114_registry():
    from backend.ai_engine.v3.corpus_release import load_candidate_corpus

    package = load_candidate_corpus(
        CANDIDATE_MANIFEST_PATH,
        CANDIDATE_PATH,
        REGISTRY_PATH,
    )

    assert package.source_registry_checksum == _load(REGISTRY_PATH)["content_checksum"]
    assert len(package.chunks) == 13
    assert [chunk["source_id"] for chunk in package.chunks] == [
        f"src_{index:02d}" for index in range(1, 14)
    ]


def test_candidate_validator_rejects_text_outside_pr114_scope():
    from backend.ai_engine.v3.corpus_release import (
        CorpusReleaseFailure,
        validate_candidate_against_source_registry,
    )

    candidate = _load(CANDIDATE_PATH)
    registry = _load(REGISTRY_PATH)
    candidate["chunks"][0]["text"] += "新增医学解释"
    candidate["chunks"][0]["content_checksum"] = _checksum(candidate["chunks"][0])
    candidate["content_checksum"] = _checksum(candidate)

    with pytest.raises(CorpusReleaseFailure, match="CORPUS_SOURCE_SCOPE_MISMATCH"):
        validate_candidate_against_source_registry(candidate, registry)


@pytest.mark.parametrize(
    ("field", "error_code"),
    [
        ("source_id", "CORPUS_SOURCE_ID_MISMATCH"),
        ("source_content_hash", "CORPUS_SOURCE_HASH_MISMATCH"),
    ],
)
def test_candidate_validator_rejects_unbound_or_changed_source_metadata(field, error_code):
    from backend.ai_engine.v3.corpus_release import (
        CorpusReleaseFailure,
        validate_candidate_against_source_registry,
    )

    candidate = _load(CANDIDATE_PATH)
    registry = _load(REGISTRY_PATH)
    candidate["chunks"][0][field] = "tampered"
    candidate["chunks"][0]["content_checksum"] = _checksum(candidate["chunks"][0])
    candidate["content_checksum"] = _checksum(candidate)

    with pytest.raises(CorpusReleaseFailure, match=error_code):
        validate_candidate_against_source_registry(candidate, registry)


def test_candidate_validator_rejects_registry_or_package_checksum_mismatch():
    from backend.ai_engine.v3.corpus_release import (
        CorpusReleaseFailure,
        validate_candidate_against_source_registry,
    )

    candidate = _load(CANDIDATE_PATH)
    registry = _load(REGISTRY_PATH)

    tampered_registry = copy.deepcopy(registry)
    tampered_registry["content_checksum"] = "sha256:wrong"
    with pytest.raises(CorpusReleaseFailure, match="CORPUS_REGISTRY_CHECKSUM_MISMATCH"):
        validate_candidate_against_source_registry(candidate, tampered_registry)

    tampered_candidate = copy.deepcopy(candidate)
    tampered_candidate["content_checksum"] = "sha256:wrong"
    with pytest.raises(CorpusReleaseFailure, match="CORPUS_CANDIDATE_CHECKSUM_MISMATCH"):
        validate_candidate_against_source_registry(tampered_candidate, registry)


def test_candidate_cannot_be_loaded_as_production_corpus(tmp_path):
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        load_production_corpus,
    )

    candidate_manifest = tmp_path / "manifest.json"
    candidate_chunks = tmp_path / "chunks.json"
    candidate_manifest.write_text(CANDIDATE_MANIFEST_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    candidate_chunks.write_text(CANDIDATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_NOT_PRODUCTION_APPROVED"):
        load_production_corpus(candidate_manifest, candidate_chunks)

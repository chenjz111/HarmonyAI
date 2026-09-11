"""Tests for the approved V3.1 Chroma index builder and receipt."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest


class FakeEmbedding:
    dimension = 1024

    def __init__(self):
        self.input_types: list[str] = []

    def embed(self, text, *, input_type):
        del text
        self.input_types.append(input_type)
        return [0.1] * self.dimension


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.rows = {}
        self.metadata = {}

    def upsert(self, *, ids, documents, metadatas, embeddings):
        for row in zip(ids, documents, metadatas, embeddings):
            self.rows[row[0]] = row

    def count(self):
        return len(self.rows)

    def get(self, *, ids, include):
        del include
        rows = [self.rows[item] for item in ids if item in self.rows]
        return {
            "ids": [row[0] for row in rows],
            "metadatas": [row[2] for row in rows],
        }


class FakeClient:
    def __init__(self):
        self.collections = {}

    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del embedding_function
        self.collections.setdefault(name, FakeCollection(name))
        self.collections[name].metadata = dict(metadata)
        return self.collections[name]


def _checksum(payload, field):
    data = {key: value for key, value in payload.items() if key != field}
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(raw.encode('utf-8')).hexdigest()}"


def _chunk(chunk_id="chunk_001"):
    from backend.app.schemas.v3.diagnosis import KnowledgeChunk

    payload = {
        "chunk_id": chunk_id,
        "source_id": "src_001",
        "source_title": "approved source",
        "section": "section-1",
        "text": "approved explanation text",
        "display_summary": "approved explanation",
        "claim_codes": ["unrefreshing_sleep"],
        "organ_codes": ["heart"],
        "review_status": "approved",
        "medical_review_version": "medical_v3.1-r1",
        "knowledge_version": "medical_v3.1",
        "content_checksum": "",
    }
    payload["content_checksum"] = _checksum(payload, "content_checksum")
    return KnowledgeChunk.model_validate(payload)


def _manifest(chunks):
    from backend.app.schemas.v3.diagnosis import IngestionManifest

    payload = {
        "knowledge_version": "medical_v3.1",
        "embedding_provider": "aliyun",
        "embedding_model": "text-embedding-v4",
        "embedding_version": "text-embedding-v4@1024",
        "distance_metric": "cosine",
        "retrieval_score_semantics": "normalized_similarity",
        "minimum_score": 0.5,
        "chunk_count": len(chunks),
        "manifest_checksum": "",
        "review_status": "approved",
    }
    payload["manifest_checksum"] = _checksum(payload, "manifest_checksum")
    return IngestionManifest.model_validate(payload)


def test_index_receipt_checksum_is_stable_and_contains_no_secret_or_vector():
    from backend.ai_engine.v3.rag_index_receipt import (
        build_index_receipt,
        canonical_index_checksum,
    )

    chunk = _chunk()
    receipt = build_index_receipt(_manifest([chunk]), [chunk], "collection_v31")
    payload = receipt.model_dump(mode="json")

    assert payload["index_checksum"] == canonical_index_checksum(payload)
    serialized = json.dumps(payload).lower()
    assert "api_key" not in serialized
    assert "embedding_vector" not in serialized
    assert "vector" not in serialized


def test_index_builder_uses_document_embedding_and_verifies_count(monkeypatch, tmp_path):
    import backend.ai_engine.v3.rag_index_cli as index_cli

    chunks = [_chunk(f"chunk_{index:03d}") for index in range(1, 14)]
    manifest = _manifest(chunks)
    embedding = FakeEmbedding()
    client = FakeClient()
    monkeypatch.setattr(index_cli, "load_production_corpus", lambda *_: (manifest, chunks))

    receipt = index_cli.build_index(
        manifest_path="approved-manifest.json",
        chunks_path="approved-chunks.json",
        persist_directory=str(tmp_path / "chroma"),
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=client,
        receipt_path=tmp_path / "receipt.json",
    )

    assert embedding.input_types == ["document"] * 13
    assert receipt.chunk_count == 13
    assert json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))["chunk_count"] == 13


def test_index_builder_rejects_candidate_before_provider_calls(tmp_path):
    import backend.ai_engine.v3.rag_index_cli as index_cli

    class ExplodingEmbedding(FakeEmbedding):
        def embed(self, text, *, input_type):
            raise AssertionError("candidate corpus must fail before embedding")

    with pytest.raises(index_cli.IndexBuildFailure, match="CORPUS_NOT_PRODUCTION_APPROVED"):
        index_cli.build_index(
            manifest_path=Path("knowledge/v3/rag-ingestion-manifest-v3.1-candidate.json"),
            chunks_path=Path("knowledge/v3/rag-corpus-chunks-v3.1-candidate.json"),
            persist_directory=str(tmp_path / "chroma"),
            collection_name="harmony_v31",
            embedding_provider=ExplodingEmbedding(),
            client=FakeClient(),
        )


def test_index_builder_rejects_non_1024_provider(monkeypatch, tmp_path):
    import backend.ai_engine.v3.rag_index_cli as index_cli

    class WrongDimension(FakeEmbedding):
        dimension = 1536

    chunk = _chunk()
    manifest = _manifest([chunk])
    monkeypatch.setattr(index_cli, "load_production_corpus", lambda *_: (manifest, [chunk]))

    with pytest.raises(index_cli.IndexBuildFailure, match="EMBEDDING_DIMENSION_INVALID"):
        index_cli.build_index(
            manifest_path="approved-manifest.json",
            chunks_path="approved-chunks.json",
            persist_directory=str(tmp_path / "chroma"),
            collection_name="harmony_v31",
            embedding_provider=WrongDimension(),
            client=FakeClient(),
        )


def test_index_builder_fails_when_collection_count_is_not_manifest_count(monkeypatch, tmp_path):
    import backend.ai_engine.v3.rag_index_cli as index_cli

    class DroppingCollection(FakeCollection):
        def upsert(self, *, ids, documents, metadatas, embeddings):
            super().upsert(ids=ids[:-1], documents=documents[:-1], metadatas=metadatas[:-1], embeddings=embeddings[:-1])

    class DroppingClient(FakeClient):
        def get_or_create_collection(self, *, name, metadata, embedding_function):
            del embedding_function
            self.collections.setdefault(name, DroppingCollection(name))
            self.collections[name].metadata = dict(metadata)
            return self.collections[name]

    chunks = [_chunk("chunk_001"), _chunk("chunk_002")]
    manifest = _manifest(chunks)
    monkeypatch.setattr(index_cli, "load_production_corpus", lambda *_: (manifest, chunks))

    with pytest.raises(index_cli.IndexBuildFailure, match="RAG_INDEX_COUNT_MISMATCH"):
        index_cli.build_index(
            manifest_path="approved-manifest.json",
            chunks_path="approved-chunks.json",
            persist_directory=str(tmp_path / "chroma"),
            collection_name="harmony_v31",
            embedding_provider=FakeEmbedding(),
            client=DroppingClient(),
        )

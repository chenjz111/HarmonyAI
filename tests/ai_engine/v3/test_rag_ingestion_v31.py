import pytest


def _manifest(*, review_status="approved", embedding_version="text-embedding-v4@1024"):
    from backend.app.schemas.v3.diagnosis import IngestionManifest

    return IngestionManifest(
        knowledge_version="medical_v3.1",
        embedding_provider="aliyun",
        embedding_model="text-embedding-v4",
        embedding_version=embedding_version,
        distance_metric="cosine",
        retrieval_score_semantics="normalized_similarity",
        minimum_score=0.5,
        chunk_count=1,
        manifest_checksum="sha256:manifest-v31",
        review_status=review_status,
    )


def _chunk(*, review_status="approved"):
    from backend.app.schemas.v3.diagnosis import KnowledgeChunk

    return KnowledgeChunk(
        chunk_id="chunk_001",
        source_id="src_001",
        source_title="approved source",
        section="section-1",
        text="approved explanation text",
        display_summary="approved explanation",
        claim_codes=["unrefreshing_sleep"],
        organ_codes=["heart"],
        review_status=review_status,
        medical_review_version="medical_v3.1-r1",
        knowledge_version="medical_v3.1",
        content_checksum="sha256:chunk-001",
    )


def test_production_ingestion_requires_owner_approved_manifest():
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        validate_production_corpus,
    )

    pending_manifest = _manifest().model_dump(mode="json")
    pending_manifest["review_status"] = "pending"
    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_NOT_PRODUCTION_APPROVED"):
        validate_production_corpus(pending_manifest, [_chunk()])


def test_production_ingestion_requires_exact_chunk_count_and_approved_chunks():
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        validate_production_corpus,
    )

    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_CHUNK_COUNT_MISMATCH"):
        validate_production_corpus(_manifest(), [])

    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_CHUNK_NOT_APPROVED"):
        validate_production_corpus(_manifest(), [{**_chunk().model_dump(), "review_status": "pending"}])


def test_production_ingestion_rejects_demo_hash_embedding_identity():
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        validate_production_corpus,
    )

    with pytest.raises(ProductionCorpusNotReady, match="EMBEDDING_NOT_APPROVED"):
        validate_production_corpus(
            _manifest(embedding_version="hash-v1@64"),
            [_chunk()],
        )


def test_production_ingestion_requires_approved_text_embedding_v4_1024_identity():
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        validate_production_corpus,
    )

    with pytest.raises(ProductionCorpusNotReady, match="EMBEDDING_NOT_APPROVED"):
        validate_production_corpus(
            _manifest(embedding_version="text-embedding-v4@1536"),
            [_chunk()],
        )


def test_load_production_corpus_reads_manifest_and_chunk_files(tmp_path):
    from backend.ai_engine.v3.rag_ingestion import load_production_corpus

    manifest_path = tmp_path / "manifest.json"
    chunks_path = tmp_path / "chunks.json"
    manifest_path.write_text(
        __import__("json").dumps(_manifest().model_dump(mode="json")),
        encoding="utf-8",
    )
    chunks_path.write_text(
        __import__("json").dumps({"chunks": [_chunk().model_dump(mode="json")]}),
        encoding="utf-8",
    )

    manifest, chunks = load_production_corpus(manifest_path, chunks_path)

    assert manifest.knowledge_version == "medical_v3.1"
    assert [chunk.chunk_id for chunk in chunks] == ["chunk_001"]


def test_load_production_corpus_rejects_missing_or_malformed_files(tmp_path):
    from backend.ai_engine.v3.rag_ingestion import (
        ProductionCorpusNotReady,
        load_production_corpus,
    )

    manifest_path = tmp_path / "manifest.json"
    chunks_path = tmp_path / "chunks.json"
    manifest_path.write_text("{", encoding="utf-8")
    chunks_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ProductionCorpusNotReady, match="CORPUS_FILES_INVALID"):
        load_production_corpus(manifest_path, chunks_path)

"""Validation gates for the Owner-approved V3.1 RAG corpus."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from backend.app.schemas.v3.diagnosis import IngestionManifest, KnowledgeChunk


class ProductionCorpusNotReady(RuntimeError):
    """The corpus cannot be used as a production medical index."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


def validate_production_corpus(
    manifest: IngestionManifest | Mapping[str, object],
    chunks: Sequence[KnowledgeChunk | Mapping[str, object]],
) -> IngestionManifest:
    """Validate an immutable manifest/chunk set before production ingestion."""

    raw_manifest = (
        manifest.model_dump(mode="json")
        if isinstance(manifest, IngestionManifest)
        else dict(manifest)
    )
    if raw_manifest.get("review_status") != "approved":
        raise ProductionCorpusNotReady(
            "CORPUS_NOT_PRODUCTION_APPROVED",
            "医学语料尚未获得生产放行。",
        )
    try:
        checked_manifest = IngestionManifest.model_validate(raw_manifest)
    except ValidationError as error:
        raise ProductionCorpusNotReady(
            "CORPUS_MANIFEST_INVALID",
            "医学语料清单格式无效。",
        ) from error

    if (
        checked_manifest.embedding_model != "text-embedding-v4"
        or checked_manifest.embedding_version != "text-embedding-v4@1024"
    ):
        raise ProductionCorpusNotReady(
            "EMBEDDING_NOT_APPROVED",
            "生产医学语料必须使用已批准的 text-embedding-v4 1024 维 Embedding。",
        )
    if len(chunks) != checked_manifest.chunk_count:
        raise ProductionCorpusNotReady(
            "CORPUS_CHUNK_COUNT_MISMATCH",
            "医学语料块数量与清单不一致。",
        )

    for raw_chunk in chunks:
        raw = (
            raw_chunk.model_dump(mode="json")
            if isinstance(raw_chunk, KnowledgeChunk)
            else dict(raw_chunk)
        )
        if raw.get("review_status") != "approved":
            raise ProductionCorpusNotReady(
                "CORPUS_CHUNK_NOT_APPROVED",
                "存在尚未批准的医学语料块。",
            )
        try:
            chunk = KnowledgeChunk.model_validate(raw)
        except ValidationError as error:
            raise ProductionCorpusNotReady(
                "CORPUS_CHUNK_INVALID",
                "医学语料块格式无效。",
            ) from error
        if chunk.knowledge_version != checked_manifest.knowledge_version:
            raise ProductionCorpusNotReady(
                "CORPUS_VERSION_MISMATCH",
                "医学语料块版本与清单不一致。",
            )

    return checked_manifest

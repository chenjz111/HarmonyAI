"""Deterministic, secret-free receipts for an approved V3.1 Chroma index."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import Field

from backend.app.schemas.v3.common import NonEmptyString, V3BaseModel
from backend.app.schemas.v3.diagnosis import IngestionManifest, KnowledgeChunk


class IndexChunkChecksum(V3BaseModel):
    chunk_id: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]


class IndexReceipt(V3BaseModel):
    schema_version: Literal["v31_chroma_index_receipt_v1"]
    collection_name: NonEmptyString
    knowledge_version: NonEmptyString
    embedding_model: Literal["text-embedding-v4"]
    embedding_dimension: Literal[1024]
    embedding_version: Literal["text-embedding-v4@1024"]
    distance_metric: Literal["cosine"]
    corpus_manifest_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    chunk_count: Annotated[int, Field(ge=0)]
    chunk_checksums: list[IndexChunkChecksum]
    index_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]


def _payload_for_checksum(payload: Mapping[str, object]) -> dict[str, object]:
    canonical = {
        key: value for key, value in payload.items() if key != "index_checksum"
    }
    if isinstance(canonical.get("chunk_checksums"), list):
        canonical["chunk_checksums"] = sorted(
            canonical["chunk_checksums"],
            key=lambda item: str(item.get("chunk_id", ""))
            if isinstance(item, Mapping)
            else "",
        )
    return canonical


def canonical_index_checksum(payload: IndexReceipt | Mapping[str, object]) -> str:
    """Hash the receipt identity without timestamps, vectors or credentials."""

    raw = (
        payload.model_dump(mode="json")
        if isinstance(payload, IndexReceipt)
        else dict(payload)
    )
    encoded = json.dumps(
        _payload_for_checksum(raw),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def build_index_receipt(
    manifest: IngestionManifest,
    chunks: Sequence[KnowledgeChunk],
    collection_name: str,
) -> IndexReceipt:
    """Build a deterministic logical receipt for an already verified index."""

    payload: dict[str, object] = {
        "schema_version": "v31_chroma_index_receipt_v1",
        "collection_name": collection_name,
        "knowledge_version": manifest.knowledge_version,
        "embedding_model": manifest.embedding_model,
        "embedding_dimension": 1024,
        "embedding_version": manifest.embedding_version,
        "distance_metric": manifest.distance_metric,
        "corpus_manifest_checksum": manifest.manifest_checksum,
        "chunk_count": len(chunks),
        "chunk_checksums": [
            {
                "chunk_id": chunk.chunk_id,
                "content_checksum": chunk.content_checksum,
            }
            for chunk in sorted(chunks, key=lambda item: item.chunk_id)
        ],
    }
    payload["index_checksum"] = canonical_index_checksum(payload)
    return IndexReceipt.model_validate(payload)

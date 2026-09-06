"""Versioned Chroma boundary for the V3.1 approved RAG corpus."""

from __future__ import annotations

from collections.abc import Sequence
import re
import uuid

from backend.app.schemas.v3.common import Degradation
from backend.app.schemas.v3.diagnosis import (
    IngestionManifest,
    KnowledgeChunk,
    RagHit,
    RagQuery,
    RagResult,
)
from backend.ai_engine.v3.rag_ingestion import validate_production_corpus


class RagStoreFailure(RuntimeError):
    """Stable store failure that contains no user source text."""

    def __init__(self, error_code: str, safe_message: str) -> None:
        self.error_code = error_code
        self.safe_message = safe_message
        super().__init__(f"{error_code}: {safe_message}")


class VersionedRagStore:
    """Chroma store whose collection identity is bound to the manifest."""

    def __init__(
        self,
        *,
        persist_directory: str,
        collection_name: str,
        embedding_provider,
        client=None,
        production: bool = True,
    ) -> None:
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.production = production
        self._client = client or self._build_client(persist_directory)
        self._collection = None
        self._manifest: IngestionManifest | None = None

    def ingest(
        self,
        manifest: IngestionManifest,
        chunks: Sequence[KnowledgeChunk],
    ) -> str:
        if self.production:
            checked = validate_production_corpus(manifest, chunks)
        else:
            checked = IngestionManifest.model_validate(manifest)
            if len(chunks) != checked.chunk_count:
                raise RagStoreFailure(
                    "CORPUS_CHUNK_COUNT_MISMATCH",
                    "医学语料块数量与清单不一致。",
                )
        collection_name = self._versioned_collection_name(checked)
        try:
            collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "knowledge_version": checked.knowledge_version,
                    "embedding_version": checked.embedding_version,
                    "manifest_checksum": checked.manifest_checksum,
                },
                embedding_function=None,
            )
            embeddings = [
                self.embedding_provider.embed(chunk.text, input_type="document")
                for chunk in chunks
            ]
            collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {
                        "source_id": chunk.source_id,
                        "source_title": chunk.source_title,
                        "section": chunk.section,
                        "display_summary": chunk.display_summary,
                        "review_status": chunk.review_status,
                        "knowledge_version": chunk.knowledge_version,
                        "content_checksum": chunk.content_checksum,
                    }
                    for chunk in chunks
                ],
                embeddings=embeddings,
            )
        except RagStoreFailure:
            raise
        except Exception as error:
            raise RagStoreFailure(
                "RAG_INDEX_UNAVAILABLE",
                "RAG 索引暂时不可用。",
            ) from error
        self._manifest = checked
        self._collection = collection
        return collection_name

    def query(self, query: RagQuery) -> RagResult:
        manifest = self._manifest
        if manifest is None or self._collection is None:
            raise RagStoreFailure("RAG_NOT_READY", "RAG 索引尚未准备就绪。")
        if query.knowledge_version != manifest.knowledge_version:
            raise RagStoreFailure("RAG_KNOWLEDGE_VERSION_MISMATCH", "RAG 知识版本不一致。")
        if query.ingestion_manifest_checksum != manifest.manifest_checksum:
            raise RagStoreFailure("RAG_MANIFEST_MISMATCH", "RAG 清单版本不一致。")
        try:
            query_vector = self.embedding_provider.embed(
                self._query_text(query),
                input_type="query",
            )
            count = int(self._collection.count())
            if count <= 0:
                return self._result("empty", [])
            raw = self._collection.query(
                query_embeddings=[query_vector],
                n_results=min(query.top_k, count),
                include=["documents", "metadatas", "distances"],
            )
        except RagStoreFailure:
            raise
        except Exception as error:
            raise RagStoreFailure("RAG_INDEX_UNAVAILABLE", "RAG 索引暂时不可用。") from error

        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        ids = (raw.get("ids") or [[]])[0]
        hits: list[RagHit] = []
        for index, (document, metadata, distance) in enumerate(
            zip(documents, metadatas, distances)
        ):
            score = 1.0 / (1.0 + float(distance))
            metadata = metadata or {}
            if score < manifest.minimum_score or metadata.get("review_status") != "approved":
                continue
            if index >= len(ids):
                raise RagStoreFailure(
                    "RAG_INVALID_RESULT",
                    "RAG 返回结果缺少稳定标识。",
                )
            hits.append(
                RagHit(
                    chunk_id=str(ids[index]),
                    source_id=str(metadata["source_id"]),
                    source_title=str(metadata["source_title"]),
                    section=str(metadata["section"]),
                    retrieval_score=score,
                    text=str(document),
                    display_summary=str(metadata["display_summary"]),
                    review_status="approved",
                )
            )
        return self._result("success" if hits else "empty", hits)

    def _result(self, status: str, hits: list[RagHit]) -> RagResult:
        assert self._manifest is not None
        return RagResult(
            retrieval_id=f"rag_{uuid.uuid4().hex}",
            status=status,
            knowledge_version=self._manifest.knowledge_version,
            embedding_version=self._manifest.embedding_version,
            retrieval_score_semantics=self._manifest.retrieval_score_semantics,
            hits=hits,
            degradation=Degradation(active=False, reason_codes=[]),
        )

    @staticmethod
    def _query_text(query: RagQuery) -> str:
        parts = [*query.organ_codes, *query.claim_codes]
        return " ".join(str(part) for part in parts) or query.query_id

    def _versioned_collection_name(self, manifest: IngestionManifest) -> str:
        identity = "_".join(
            (
                self.collection_name,
                manifest.knowledge_version,
                manifest.embedding_version,
                f"d{getattr(self.embedding_provider, 'dimension', 0)}",
            )
        )
        return re.sub(r"[^A-Za-z0-9_.-]", "_", identity)

    @staticmethod
    def _build_client(persist_directory: str):
        import chromadb

        return chromadb.PersistentClient(path=persist_directory)

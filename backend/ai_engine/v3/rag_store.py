"""Versioned Chroma boundary for the V3.1 approved RAG corpus."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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


CHROMA_DISTANCE_METADATA_KEY = "hnsw:space"
APPROVED_DISTANCE_METRIC = "cosine"
SCORE_COMPARISON_EPSILON = 1e-6


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
        self._approved_chunk_ids: frozenset[str] = frozenset()
        self._medical_review_versions: frozenset[str] = frozenset()
        self._chunk_checksums: dict[str, str] = {}
        self._active_collection_name: str | None = None

    @property
    def manifest(self) -> IngestionManifest | None:
        """The validated manifest bound to the active Chroma collection."""

        return self._manifest

    @property
    def approved_chunk_ids(self) -> frozenset[str]:
        """Chunk identifiers admitted by the last validated corpus ingest."""

        return self._approved_chunk_ids

    @property
    def medical_review_versions(self) -> frozenset[str]:
        """Medical review releases represented by the active corpus."""

        return self._medical_review_versions

    @property
    def chunk_checksums(self) -> Mapping[str, str]:
        """Checksums for chunks admitted to the active collection."""

        return dict(self._chunk_checksums)

    @property
    def active_collection_name(self) -> str | None:
        """The concrete versioned Chroma collection name after ingest."""

        return self._active_collection_name

    @property
    def collection_count(self) -> int:
        """Current Chroma row count, or zero before an ingest."""

        if self._collection is None:
            return 0
        try:
            return int(self._collection.count())
        except Exception as error:
            raise RagStoreFailure(
                "RAG_INDEX_UNAVAILABLE",
                "RAG 索引暂时不可用。",
            ) from error

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
        if checked.distance_metric != APPROVED_DISTANCE_METRIC:
            raise RagStoreFailure(
                "RAG_DISTANCE_METRIC_NOT_APPROVED",
                "RAG 索引必须使用已批准的 cosine 距离。",
            )
        checked_chunks = [KnowledgeChunk.model_validate(chunk) for chunk in chunks]
        incoming_checksums = {
            chunk.chunk_id: chunk.content_checksum for chunk in checked_chunks
        }
        if (
            self._manifest is not None
            and self._collection is not None
            and self._manifest.manifest_checksum == checked.manifest_checksum
            and self._chunk_checksums == incoming_checksums
        ):
            return self._versioned_collection_name(checked)
        collection_name = self._versioned_collection_name(checked)
        try:
            collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "knowledge_version": checked.knowledge_version,
                    "embedding_version": checked.embedding_version,
                    "manifest_checksum": checked.manifest_checksum,
                    CHROMA_DISTANCE_METADATA_KEY: APPROVED_DISTANCE_METRIC,
                },
                embedding_function=None,
            )
            self._assert_cosine_collection(collection)
            if self._collection_matches(collection, checked_chunks, checked):
                self._bind_collection(collection, checked, checked_chunks, collection_name)
                return collection_name
            embeddings = [
                self.embedding_provider.embed(chunk.text, input_type="document")
                for chunk in checked_chunks
            ]
            collection.upsert(
                ids=[chunk.chunk_id for chunk in checked_chunks],
                documents=[chunk.text for chunk in checked_chunks],
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
                    for chunk in checked_chunks
                ],
                embeddings=embeddings,
            )
            if int(collection.count()) != checked.chunk_count:
                raise RagStoreFailure(
                    "RAG_INDEX_COUNT_MISMATCH",
                    "Chroma 索引数量与医学语料清单不一致。",
                )
        except RagStoreFailure:
            raise
        except Exception as error:
            raise RagStoreFailure(
                "RAG_INDEX_UNAVAILABLE",
                "RAG 索引暂时不可用。",
            ) from error
        self._bind_collection(collection, checked, checked_chunks, collection_name)
        return collection_name

    def _bind_collection(
        self,
        collection,
        manifest: IngestionManifest,
        chunks: Sequence[KnowledgeChunk],
        collection_name: str,
    ) -> None:
        self._manifest = manifest
        self._approved_chunk_ids = frozenset(chunk.chunk_id for chunk in chunks)
        self._medical_review_versions = frozenset(
            chunk.medical_review_version for chunk in chunks
        )
        self._chunk_checksums = {
            chunk.chunk_id: chunk.content_checksum for chunk in chunks
        }
        self._collection = collection
        self._active_collection_name = collection_name

    @staticmethod
    def _collection_matches(collection, chunks: Sequence[KnowledgeChunk], manifest: IngestionManifest) -> bool:
        """Reuse a persisted collection only when IDs and checksums still match."""

        try:
            if int(collection.count()) != manifest.chunk_count:
                return False
            rows = collection.get(
                ids=[chunk.chunk_id for chunk in chunks],
                include=["metadatas"],
            )
            ids = list(rows.get("ids") or [])
            metadatas = list(rows.get("metadatas") or [])
            if set(ids) != {chunk.chunk_id for chunk in chunks}:
                return False
            metadata_by_id = {
                str(chunk_id): metadata or {}
                for chunk_id, metadata in zip(ids, metadatas)
            }
            return all(
                metadata_by_id[chunk.chunk_id].get("content_checksum")
                == chunk.content_checksum
                and metadata_by_id[chunk.chunk_id].get("knowledge_version")
                == manifest.knowledge_version
                and metadata_by_id[chunk.chunk_id].get("review_status") == "approved"
                for chunk in chunks
            )
        except Exception:
            return False

    def query(self, query: RagQuery) -> RagResult:
        manifest = self._manifest
        if manifest is None or self._collection is None:
            raise RagStoreFailure("RAG_NOT_READY", "RAG 索引尚未准备就绪。")
        if query.knowledge_version != manifest.knowledge_version:
            raise RagStoreFailure("RAG_KNOWLEDGE_VERSION_MISMATCH", "RAG 知识版本不一致。")
        if query.ingestion_manifest_checksum != manifest.manifest_checksum:
            raise RagStoreFailure("RAG_MANIFEST_MISMATCH", "RAG 清单版本不一致。")
        self._assert_cosine_collection(self._collection)
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
            cosine_distance = float(distance)
            cosine_similarity = 1.0 - cosine_distance
            score = 1.0 / (2.0 - cosine_similarity)
            metadata = metadata or {}
            if (
                score + SCORE_COMPARISON_EPSILON < manifest.minimum_score
                or metadata.get("review_status") != "approved"
            ):
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
        return " ".join(str(getattr(part, "value", part)) for part in parts) or query.query_id

    @staticmethod
    def _assert_cosine_collection(collection) -> None:
        metadata = getattr(collection, "metadata", None)
        if not isinstance(metadata, Mapping) or metadata.get(CHROMA_DISTANCE_METADATA_KEY) != APPROVED_DISTANCE_METRIC:
            raise RagStoreFailure(
                "RAG_DISTANCE_METRIC_MISMATCH",
                "RAG 索引距离配置不是 cosine。",
            )

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

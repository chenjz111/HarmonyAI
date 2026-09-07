import pytest


class FakeEmbedding:
    dimension = 1024

    def __init__(self):
        self.input_types = []

    def embed(self, text, *, input_type):
        self.input_types.append(input_type)
        return [0.1] * self.dimension


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.rows = {}

    def upsert(self, *, ids, documents, metadatas, embeddings):
        for row in zip(ids, documents, metadatas, embeddings):
            self.rows[row[0]] = row

    def count(self):
        return len(self.rows)

    def query(self, *, query_embeddings, n_results, include):
        del query_embeddings, n_results, include
        row = next(iter(self.rows.values()))
        return {
            "ids": [[row[0]]],
            "documents": [[row[1]]],
            "metadatas": [[row[2]]],
            "distances": [[0.1]],
        }


class MultiResultCollection(FakeCollection):
    def query(self, *, query_embeddings, n_results, include):
        del query_embeddings, n_results, include
        rows = list(self.rows.values())
        return {
            "ids": [[row[0] for row in rows]],
            "documents": [[row[1] for row in rows]],
            "metadatas": [[row[2] for row in rows]],
            "distances": [[10.0, 0.1]],
        }


class FakeClient:
    def __init__(self):
        self.collections = {}

    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del metadata, embedding_function
        self.collections.setdefault(name, FakeCollection(name))
        return self.collections[name]


class MultiResultClient(FakeClient):
    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del metadata, embedding_function
        self.collections.setdefault(name, MultiResultCollection(name))
        return self.collections[name]


def _manifest(chunk_count=1):
    from backend.app.schemas.v3.diagnosis import IngestionManifest

    return IngestionManifest(
        knowledge_version="medical_v3.1",
        embedding_provider="aliyun",
        embedding_model="text-embedding-v4",
        embedding_version="text-embedding-v4@1024",
        distance_metric="cosine",
        retrieval_score_semantics="normalized_similarity",
        minimum_score=0.5,
        chunk_count=chunk_count,
        manifest_checksum="sha256:manifest-v31",
        review_status="approved",
    )


def _chunk(chunk_id="chunk_001"):
    from backend.app.schemas.v3.diagnosis import KnowledgeChunk

    return KnowledgeChunk(
        chunk_id=chunk_id,
        source_id="src_001",
        source_title="approved source",
        section="section-1",
        text="approved explanation text",
        display_summary="approved explanation",
        claim_codes=["unrefreshing_sleep"],
        organ_codes=["heart"],
        review_status="approved",
        medical_review_version="medical_v3.1-r1",
        knowledge_version="medical_v3.1",
        content_checksum="sha256:chunk-001",
    )


def _query():
    from backend.app.schemas.v3.diagnosis import RagQuery

    return RagQuery(
        query_id="query_001",
        knowledge_version="medical_v3.1",
        ingestion_manifest_checksum="sha256:manifest-v31",
        organ_codes=["heart"],
        claim_codes=["unrefreshing_sleep"],
        supporting_fact_ids=["fact_001"],
        contradicting_fact_ids=[],
        top_k=3,
    )


def test_versioned_rag_store_isolates_collection_by_manifest_and_embedding_identity():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    client = FakeClient()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=client,
        production=False,
    )

    store.ingest(_manifest(), [_chunk()])

    assert len(client.collections) == 1
    collection_name = next(iter(client.collections))
    assert "medical_v3.1" in collection_name
    assert "text-embedding-v4_1024" in collection_name


def test_versioned_rag_store_uses_document_embedding_for_ingestion_and_query_embedding_for_retrieval():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    embedding = FakeEmbedding()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=FakeClient(),
        production=False,
    )
    store.ingest(_manifest(), [_chunk()])

    result = store.query(_query())

    assert result.status == "success"
    assert result.hits[0].chunk_id == "chunk_001"
    assert embedding.input_types == ["document", "query"]


def test_versioned_rag_store_reuses_matching_manifest_without_reembedding():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    embedding = FakeEmbedding()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=FakeClient(),
        production=False,
    )

    store.ingest(_manifest(), [_chunk()])
    store.ingest(_manifest(), [_chunk()])

    assert embedding.input_types == ["document"]


def test_versioned_rag_store_rejects_manifest_mismatch_without_returning_hits():
    from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore

    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=FakeClient(),
        production=False,
    )
    store.ingest(_manifest(), [_chunk()])
    query = _query().model_copy(update={"ingestion_manifest_checksum": "sha256:other"})

    with pytest.raises(RagStoreFailure, match="RAG_MANIFEST_MISMATCH"):
        store.query(query)


def test_versioned_rag_store_preserves_chunk_ids_after_filtering_low_score_hits():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=MultiResultClient(),
        production=False,
    )
    store.ingest(_manifest(chunk_count=2), [_chunk(), _chunk("chunk_002")])

    result = store.query(_query())

    assert [hit.chunk_id for hit in result.hits] == ["chunk_002"]

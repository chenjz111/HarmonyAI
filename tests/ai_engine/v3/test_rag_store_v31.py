import pytest


class FakeEmbedding:
    dimension = 1024

    def __init__(self):
        self.input_types = []
        self.texts = []

    def embed(self, text, *, input_type):
        self.input_types.append(input_type)
        self.texts.append(text)
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


class BoundaryCollection(FakeCollection):
    def query(self, *, query_embeddings, n_results, include):
        del query_embeddings, n_results, include
        row = next(iter(self.rows.values()))
        return {
            "ids": [[row[0]]],
            "documents": [[row[1]]],
            "metadatas": [[row[2]]],
            # Chroma cosine distance for raw cosine similarity 0.65.
            "distances": [[0.35]],
        }


class FakeClient:
    def __init__(self):
        self.collections = {}

    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del embedding_function
        self.collections.setdefault(name, FakeCollection(name))
        self.collections[name].metadata = dict(metadata)
        return self.collections[name]


class MultiResultClient(FakeClient):
    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del embedding_function
        self.collections.setdefault(name, MultiResultCollection(name))
        self.collections[name].metadata = dict(metadata)
        return self.collections[name]


class BoundaryClient(FakeClient):
    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del embedding_function
        self.collections.setdefault(name, BoundaryCollection(name))
        self.collections[name].metadata = dict(metadata)
        return self.collections[name]


class WrongDistanceClient(FakeClient):
    def get_or_create_collection(self, *, name, metadata, embedding_function):
        collection = super().get_or_create_collection(
            name=name, metadata=metadata, embedding_function=embedding_function
        )
        collection.metadata["hnsw:space"] = "l2"
        return collection


class ScenarioCollection(FakeCollection):
    def __init__(self, name, distance):
        super().__init__(name)
        self.distance = distance

    def query(self, *, query_embeddings, n_results, include):
        del query_embeddings, n_results, include
        row = next(iter(self.rows.values()))
        return {
            "ids": [[row[0]]],
            "documents": [[row[1]]],
            "metadatas": [[row[2]]],
            "distances": [[self.distance]],
        }


class ScenarioClient(FakeClient):
    def __init__(self, distance):
        super().__init__()
        self.distance = distance

    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del embedding_function
        self.collections.setdefault(name, ScenarioCollection(name, self.distance))
        self.collections[name].metadata = dict(metadata)
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


def test_versioned_rag_store_creates_collection_with_explicit_cosine_distance():
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

    collection = next(iter(client.collections.values()))
    assert collection.metadata["hnsw:space"] == "cosine"


def test_versioned_rag_store_rejects_existing_non_cosine_collection():
    from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore

    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=WrongDistanceClient(),
        production=False,
    )

    with pytest.raises(RagStoreFailure, match="RAG_DISTANCE_METRIC_MISMATCH"):
        store.ingest(_manifest(), [_chunk()])


def test_versioned_rag_store_rejects_non_cosine_manifest_before_indexing():
    from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore

    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=FakeClient(),
        production=False,
    )

    with pytest.raises(RagStoreFailure, match="RAG_DISTANCE_METRIC_NOT_APPROVED"):
        store.ingest(_manifest().model_copy(update={"distance_metric": "l2"}), [_chunk()])


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


def test_versioned_rag_store_serializes_organ_enum_as_value():
    from backend.ai_engine.v3.rag_store import VersionedRagStore
    from backend.app.schemas.v3.common import OrganCode

    embedding = FakeEmbedding()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=FakeClient(),
        production=False,
    )
    store.ingest(_manifest(), [_chunk()])
    query = _query().model_copy(update={"organ_codes": [OrganCode.heart]})

    store.query(query)

    assert "OrganCode.heart" not in embedding.texts[-1]
    assert "heart" not in embedding.texts[-1]
    assert "unrefreshing_sleep" not in embedding.texts[-1]
    assert embedding.texts[-1] == (
        "已批准资料中关于心与睡眠不解乏的状态关联和相关说明。"
    )


def test_versioned_rag_store_uses_only_approved_display_semantics_for_query():
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

    store.query(_query())

    assert embedding.texts[-1] == (
        "已批准资料中关于心与睡眠不解乏的状态关联和相关说明。"
    )
    assert all(
        forbidden not in embedding.texts[-1]
        for forbidden in ("help me sleep", "raw ocr", "free narrative")
    )


def test_versioned_rag_store_rejects_missing_approved_query_mapping():
    from backend.ai_engine.v3.rag_store import RagStoreFailure, VersionedRagStore

    embedding = FakeEmbedding()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=FakeClient(),
        production=False,
        claim_display_names={},
        organ_display_names={"heart": "心"},
    )
    store.ingest(_manifest(), [_chunk()])

    with pytest.raises(RagStoreFailure, match="RAG_QUERY_MAPPING_NOT_APPROVED"):
        store.query(_query())

    assert embedding.input_types == ["document"]


def test_versioned_rag_store_query_text_is_deterministic():
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

    store.query(_query())
    store.query(_query())

    expected = "已批准资料中关于心与睡眠不解乏的状态关联和相关说明。"
    assert embedding.texts[-2:] == [expected, expected]


def test_versioned_rag_store_uses_approved_natural_language_intent_for_liver_anger():
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

    store.query(
        _query().model_copy(
            update={
                "organ_codes": ["liver"],
                "claim_codes": ["anger_tendency"],
            }
        )
    )

    assert embedding.texts[-1] == (
        "已批准资料中关于肝与烦躁易怒倾向的五志五脏对应关系和相关说明。"
        "相关词：怒。"
    )
    assert "liver" not in embedding.texts[-1]
    assert "anger_tendency" not in embedding.texts[-1]


def test_versioned_rag_store_uses_approved_sleep_intent_for_heart_sleep_disturbance():
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

    store.query(
        _query().model_copy(
            update={
                "organ_codes": ["heart"],
                "claim_codes": ["sleep_disturbance"],
            }
        )
    )

    assert embedding.texts[-1] == (
        "已批准资料中关于心与睡眠障碍的状态关联和相关说明。"
        "相关词：不寐。"
    )
    assert "heart" not in embedding.texts[-1]
    assert "sleep_disturbance" not in embedding.texts[-1]


def test_versioned_rag_store_keeps_unsupported_unrefreshing_signal_without_approved_alias():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    embedding = FakeEmbedding()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=ScenarioClient(0.40),
        production=False,
    )
    manifest = _manifest().model_copy(update={"minimum_score": 0.740741})
    store.ingest(manifest, [_chunk()])

    result = store.query(
        _query().model_copy(
            update={
                "claim_codes": ["unrefreshing_sleep"],
                "ingestion_manifest_checksum": manifest.manifest_checksum,
            }
        )
    )

    assert result.status == "empty"
    assert result.hits == []
    assert "不寐" not in embedding.texts[-1]


def test_versioned_rag_store_applies_approved_cosine_to_runtime_score_conversion():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    manifest = _manifest().model_copy(update={"minimum_score": 0.740741})
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=BoundaryClient(),
        production=False,
    )

    store.ingest(manifest, [_chunk()])
    result = store.query(_query().model_copy(update={"ingestion_manifest_checksum": manifest.manifest_checksum}))

    assert result.status == "success"
    assert result.hits[0].retrieval_score == pytest.approx(0.7407407407)


@pytest.mark.parametrize(
    ("query_id", "cosine_distance", "expected_status"),
    [
        ("gq_02", 0.20, "success"),
        ("gq_06", 0.30, "success"),
        ("gq_13", 0.10, "success"),
        ("gq_14", 0.40, "empty"),
        ("gq_15", 0.40, "empty"),
        ("gq_17", 0.40, "empty"),
    ],
)
def test_v31_approved_threshold_has_expected_gold_query_gate(
    query_id, cosine_distance, expected_status
):
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    manifest = _manifest().model_copy(update={"minimum_score": 0.740741})
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=FakeEmbedding(),
        client=ScenarioClient(cosine_distance),
        production=False,
    )

    store.ingest(manifest, [_chunk()])
    result = store.query(
        _query().model_copy(
            update={
                "query_id": query_id,
                "ingestion_manifest_checksum": manifest.manifest_checksum,
            }
        )
    )

    assert result.status == expected_status
    if expected_status == "empty":
        assert result.hits == []


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


def test_versioned_rag_store_reuses_matching_persisted_collection_without_reembedding():
    from backend.ai_engine.v3.rag_store import VersionedRagStore

    client = FakeClient()
    first_embedding = FakeEmbedding()
    first_store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=first_embedding,
        client=client,
        production=False,
    )
    first_store.ingest(_manifest(), [_chunk()])

    second_embedding = FakeEmbedding()
    second_store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=second_embedding,
        client=client,
        production=False,
    )
    second_store.ingest(_manifest(), [_chunk()])

    assert first_embedding.input_types == ["document"]
    assert second_embedding.input_types == []
    assert second_store.collection_count == 1
    assert second_store.active_collection_name == next(iter(client.collections))

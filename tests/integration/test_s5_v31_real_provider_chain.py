import asyncio
import json


def _state_and_snapshot():
    from tests.ai_engine.v3.test_v31_pipeline import _confirmed_state, _snapshot

    manifest, _chunk = _manifest_and_chunk()
    snapshot = {
        **_snapshot(),
        "manifest_checksum": manifest.manifest_checksum,
    }
    return _confirmed_state(), snapshot


def _mapping():
    from tests.ai_engine.v3.test_v31_pipeline import _mapping

    return _mapping()


def _rules():
    from tests.ai_engine.v3.test_v31_pipeline import _rules

    return _rules()


def _manifest_and_chunk():
    from backend.ai_engine.v3.rag_ingestion import _content_checksum
    from backend.app.schemas.v3.diagnosis import IngestionManifest, KnowledgeChunk

    manifest_payload = {
        "knowledge_version": "medical_v3.1",
        "embedding_provider": "aliyun",
        "embedding_model": "text-embedding-v4",
        "embedding_version": "text-embedding-v4@1024",
        "distance_metric": "cosine",
        "retrieval_score_semantics": "normalized_similarity",
        "minimum_score": 0.5,
        "chunk_count": 1,
        "manifest_checksum": "",
        "review_status": "approved",
    }
    manifest_payload["manifest_checksum"] = _content_checksum(
        manifest_payload, "manifest_checksum"
    )
    manifest = IngestionManifest(**manifest_payload)
    chunk_payload = {
        "chunk_id": "chunk_1",
        "source_id": "source_1",
        "source_title": "approved source",
        "section": "section",
        "text": "approved corpus text",
        "display_summary": "approved summary",
        "claim_codes": ["unrefreshing_sleep"],
        "organ_codes": ["heart"],
        "review_status": "approved",
        "medical_review_version": "medical_v3.1-r1",
        "knowledge_version": "medical_v3.1",
        "content_checksum": "",
    }
    chunk_payload["content_checksum"] = _content_checksum(
        chunk_payload, "content_checksum"
    )
    chunk = KnowledgeChunk(**chunk_payload)
    return manifest, chunk


class _EmbeddingTransport:
    def __init__(self):
        self.input_types = []

    def __call__(self, url, headers, body, timeout):
        del url, timeout
        assert headers["X-DashScope-WorkSpace"] == "workspace-test"
        payload = json.loads(body)
        self.input_types.append(payload["input_type"])
        return json.dumps({"data": [{"embedding": [0.1] * 1024}]}).encode()


class _Collection:
    def __init__(self):
        self.rows = {}
        self.metadata = {}

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


class _ChromaClient:
    def __init__(self):
        self.collection = _Collection()
        self.names = []

    def get_or_create_collection(self, *, name, metadata, embedding_function):
        del embedding_function
        self.names.append(name)
        self.collection.metadata = dict(metadata)
        return self.collection


class _QwenTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        del timeout
        payload = json.loads(body)
        self.calls.append((url, headers, payload))
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "success",
                                    "candidate_tendencies": [
                                        {
                                            "syndrome_code": "syndrome_1",
                                            "display_name": "safe tendency",
                                            "relative_support": 0.8,
                                            "supporting_fact_ids": ["fact_1"],
                                            "contradicting_fact_ids": [],
                                            "knowledge_chunk_ids": ["chunk_1"],
                                            "reasoning_summary": "grounded summary",
                                        }
                                    ],
                                    "abstained": False,
                                    "abstain_reason": None,
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()


def test_mock_adapter_classes_execute_the_v31_chain_without_network_or_secrets():
    from backend.ai_engine.providers import QwenCompatibleProvider
    from backend.ai_engine.v3.diagnosis_provider import DiagnosisProvider
    from backend.ai_engine.v3.embedding_provider import EmbeddingProvider
    from backend.ai_engine.v3.rag_store import VersionedRagStore
    from backend.ai_engine.v3.v31_pipeline import execute_v31_ai_pipeline

    embedding_transport = _EmbeddingTransport()
    embedding = EmbeddingProvider(
        base_url="https://dashscope.example/compatible-mode/v1",
        api_key="configured",
        model="text-embedding-v4",
        dimension=1024,
        workspace_id="workspace-test",
        transport=embedding_transport,
    )
    chroma = _ChromaClient()
    store = VersionedRagStore(
        persist_directory="unused",
        collection_name="harmony_v31",
        embedding_provider=embedding,
        client=chroma,
        production=True,
    )
    manifest, chunk = _manifest_and_chunk()
    store.ingest(manifest, [chunk])

    qwen_transport = _QwenTransport()
    qwen_backend = QwenCompatibleProvider(
        base_url="https://dashscope.example/compatible-mode/v1",
        api_key="configured",
        model="qwen-approved",
        extra_headers={"X-DashScope-WorkSpace": "workspace-test"},
        transport=qwen_transport,
    )
    diagnosis_provider = DiagnosisProvider(
        backend=qwen_backend,
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )
    state, snapshot = _state_and_snapshot()

    result = asyncio.run(
        execute_v31_ai_pipeline(
            confirmed_user_state=state,
            assessment_snapshot=snapshot,
            rag_store=store,
            diagnosis_provider=diagnosis_provider,
            tone_mapping=_mapping(),
            generation_parameter_rules=_rules(),
        )
    )

    assert embedding_transport.input_types == ["document", "query"]
    assert any("medical_v3.1" in name for name in chroma.names)
    assert result.rag_result.status == "success"
    assert result.rag_result.hits[0].chunk_id == "chunk_1"
    assert result.diagnosis_execution.status == "success"
    assert result.read_model.primary_tone.tone.value == "zhi"
    assert qwen_transport.calls[0][1]["X-DashScope-WorkSpace"] == "workspace-test"
    assert qwen_transport.calls[0][2]["response_format"] == {"type": "json_object"}
    user_prompt = qwen_transport.calls[0][2]["messages"][1]["content"]
    assert "approved corpus text" in user_prompt
    assert "chunk_1" in user_prompt
    assert chunk.content_checksum in user_prompt

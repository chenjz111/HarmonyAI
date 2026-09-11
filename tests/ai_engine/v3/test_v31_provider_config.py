import hashlib
import json

import pytest


def _write_medical_rule_asset(tmp_path, *, version="medical-rules-v3.1-r1"):
    payload = {
        "schema_id": "medical_rules_v3.1",
        "schema_version": "3.1.0",
        "medical_rule_version": version,
        "review_status": "approved",
        "allowed_syndrome_codes": [f"syd_{index:03d}" for index in range(1, 9)],
        "syndrome_aliases": {
            "syd_001": "liver_stagnation_heat",
            "syd_002": "liver_qi_stagnation",
            "syd_003": "heart_fire_flare",
            "syd_004": "heart_spleen_deficiency",
            "syd_005": "spleen_deficiency_dampness",
            "syd_006": "lung_qi_deficiency",
            "syd_007": "kidney_yin_deficiency",
            "syd_008": "heart_kidney_discordance",
        },
        "content_checksum": "",
    }
    canonical = {key: value for key, value in payload.items() if key != "content_checksum"}
    payload["content_checksum"] = "sha256:" + hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / "medical-rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def test_v31_provider_config_requires_explicit_real_mode_configuration():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "EMBEDDING_PROVIDER": "aliyun",
            "EMBEDDING_BASE_URL": "https://embedding.example",
            "EMBEDDING_API_KEY": "configured-value",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1024",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
            "QWEN_BASE_URL": "https://qwen.example/v1",
            "QWEN_API_KEY": "configured-value",
            "QWEN_MODEL": "qwen-approved",
        }
    )

    assert config.real_agents is True
    assert config.embedding_dimension == 1024
    assert config.embedding_model == "text-embedding-v4"
    assert config.chroma_collection == "harmony_v31"
    assert config.safe_dict()["embedding_configured"] is True
    assert config.safe_dict()["qwen_model"] == "qwen-approved"
    assert "configured-value" not in str(config.safe_dict())
    assert "workspace-test" not in str(config.safe_dict())


def test_v31_provider_config_reports_missing_real_embedding_as_not_ready():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {"HARMONYAI_REAL_AGENTS": "true", "EMBEDDING_DIMENSION": "1024"}
    )

    assert config.real_agents is True
    assert config.readiness_error == "DASHSCOPE_PROVIDER_NOT_CONFIGURED"


def test_v31_provider_config_rejects_hash_embedding_in_real_mode():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "EMBEDDING_PROVIDER": "local",
            "EMBEDDING_BASE_URL": "http://embedding.example",
            "EMBEDDING_API_KEY": "secret",
            "EMBEDDING_MODEL": "hash-v1",
            "EMBEDDING_DIMENSION": "64",
        }
    )

    assert config.readiness_error == "PRODUCTION_EMBEDDING_NOT_APPROVED"


def test_v31_provider_config_reports_missing_qwen_after_embedding_and_chroma_are_ready():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "EMBEDDING_PROVIDER": "aliyun",
            "EMBEDDING_BASE_URL": "https://embedding.example",
            "EMBEDDING_API_KEY": "embedding-secret",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1024",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
        }
    )

    assert config.readiness_error == "QWEN_PROVIDER_NOT_CONFIGURED"


def test_agent_config_exposes_v31_embedding_provider_from_explicit_environment():
    from backend.app.core.agent_config import get_v31_embedding_provider

    provider = get_v31_embedding_provider(
        {
            "EMBEDDING_PROVIDER": "aliyun",
            "EMBEDDING_BASE_URL": "https://embedding.example",
            "EMBEDDING_API_KEY": "secret",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1024",
        }
    )

    assert provider is not None
    assert provider.model == "text-embedding-v4"
    assert provider.dimension == 1024


def test_agent_config_does_not_build_v31_embedding_when_provider_identity_is_missing():
    from backend.app.core.agent_config import get_v31_embedding_provider

    assert (
        get_v31_embedding_provider(
            {
                "EMBEDDING_BASE_URL": "https://embedding.example",
                "EMBEDDING_API_KEY": "secret",
                "EMBEDDING_MODEL": "text-embedding-v4",
                "EMBEDDING_DIMENSION": "1024",
            }
        )
        is None
    )


def test_agent_config_does_not_expose_unapproved_v31_embedding_provider():
    from backend.app.core.agent_config import get_v31_embedding_provider

    assert (
        get_v31_embedding_provider(
            {
                "EMBEDDING_BASE_URL": "https://embedding.example",
                "EMBEDDING_API_KEY": "secret",
                "EMBEDDING_MODEL": "hash-v1",
                "EMBEDDING_DIMENSION": "64",
            }
        )
        is None
    )


def test_v31_provider_config_requires_the_exact_production_embedding_model():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "EMBEDDING_PROVIDER": "aliyun",
            "EMBEDDING_BASE_URL": "https://embedding.example",
            "EMBEDDING_API_KEY": "secret",
            "EMBEDDING_MODEL": "text-embedding-v3",
            "EMBEDDING_DIMENSION": "1024",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
            "QWEN_BASE_URL": "https://qwen.example/v1",
            "QWEN_API_KEY": "secret",
            "QWEN_MODEL": "qwen-approved",
        }
    )

    assert config.readiness_error == "PRODUCTION_EMBEDDING_NOT_APPROVED"


def test_v31_real_rag_factory_fails_closed_without_a_production_corpus():
    from backend.app.core.agent_config import V31ReadinessFailure, get_v31_rag_store

    with pytest.raises(V31ReadinessFailure, match="RAG_CORPUS_NOT_CONFIGURED"):
        get_v31_rag_store(
            {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "EMBEDDING_PROVIDER": "aliyun",
                "EMBEDDING_BASE_URL": "https://embedding.example",
                "EMBEDDING_API_KEY": "configured-value",
                "EMBEDDING_MODEL": "text-embedding-v4",
                "EMBEDDING_DIMENSION": "1024",
                "CHROMA_PERSIST_DIRECTORY": "data/chroma",
                "CHROMA_COLLECTION": "harmony_v31",
                "QWEN_BASE_URL": "https://qwen.example/v1",
                "QWEN_API_KEY": "configured-value",
                "QWEN_MODEL": "qwen-approved",
            }
        )


def test_v31_provider_config_reads_dashscope_credentials_without_exposing_them():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "DASHSCOPE_BASE_URL": "https://dashscope.example/v1",
            "QWEN_MODEL": "qwen-approved",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
        }
    )

    assert config.readiness_error is None
    assert config.embedding_model == "text-embedding-v4"
    assert config.embedding_dimension == 1024
    assert config.safe_dict()["embedding_configured"] is True
    assert "configured-value" not in str(config.safe_dict())
    assert "workspace-test" not in str(config.safe_dict())


def test_v31_provider_config_requires_dashscope_credentials_in_real_mode():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "QWEN_MODEL": "qwen-approved",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
        }
    )

    assert config.readiness_error == "DASHSCOPE_PROVIDER_NOT_CONFIGURED"


def test_v31_real_factory_fails_with_readiness_error_when_dashscope_is_missing():
    from backend.app.core.agent_config import V31ReadinessFailure, get_v31_rag_store

    with pytest.raises(V31ReadinessFailure, match="DASHSCOPE_PROVIDER_NOT_CONFIGURED"):
        get_v31_rag_store({"HARMONYAI_REAL_AGENTS": "true"})


def test_v31_real_qwen_factory_matches_readiness_and_returns_configured_provider():
    from backend.app.core.agent_config import get_v31_diagnosis_provider

    provider = get_v31_diagnosis_provider(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "QWEN_MODEL": "qwen-approved",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
        },
        allowed_syndrome_codes={"syndrome_1"},
        allowed_fact_ids={"fact_1"},
        allowed_chunk_ids={"chunk_1"},
    )

    assert provider.backend.model == "qwen-approved"
    assert provider.backend.extra_headers["X-DashScope-WorkSpace"] == "workspace-test"


def test_v31_pipeline_factory_requires_explicit_medical_rule_release():
    from backend.app.core.agent_config import (
        V31ReadinessFailure,
        get_v31_ai_pipeline_dependencies,
    )

    with pytest.raises(V31ReadinessFailure, match="MEDICAL_RULE_ASSET_NOT_CONFIGURED"):
        get_v31_ai_pipeline_dependencies(
            {
                "HARMONYAI_REAL_AGENTS": "true",
                "DASHSCOPE_API_KEY": "configured-value",
                "DASHSCOPE_WORKSPACE_ID": "workspace-test",
                "QWEN_MODEL": "qwen-approved",
                "CHROMA_PERSIST_DIRECTORY": "data/chroma",
                "CHROMA_COLLECTION": "harmony_v31",
            }
        )


def test_v31_pipeline_factory_rejects_corpus_medical_rule_version_mismatch(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from tests.ai_engine.v3.test_music_generation_rules_v31 import (
        _payload as music_rules_payload,
        _write_payload as write_music_rules,
    )

    from backend.app.core import agent_config
    from backend.app.core.agent_config import (
        V31ReadinessFailure,
        get_v31_ai_pipeline_dependencies,
    )

    music_rules = music_rules_payload()
    rules_path = write_music_rules(tmp_path, music_rules)
    medical_rules_path, medical_rules = _write_medical_rule_asset(tmp_path)
    monkeypatch.setattr(
        "backend.app.services.v3.knowledge_assets.load_five_tone_mapping",
        lambda: {},
    )
    monkeypatch.setattr(
        agent_config,
        "get_v31_rag_store",
        lambda _environment: SimpleNamespace(
            medical_review_versions=frozenset({"medical-rules-v3.1-r0"}),
            approved_chunk_ids=frozenset(),
        ),
    )

    with pytest.raises(V31ReadinessFailure, match="MEDICAL_RULE_VERSION_MISMATCH"):
        get_v31_ai_pipeline_dependencies(
            {
                "HARMONYAI_REAL_AGENTS": "true",
                "DASHSCOPE_API_KEY": "configured-value",
                "DASHSCOPE_WORKSPACE_ID": "workspace-test",
                "QWEN_MODEL": "qwen-approved",
                "CHROMA_PERSIST_DIRECTORY": "data/chroma",
                "CHROMA_COLLECTION": "harmony_v31",
                "V31_MEDICAL_RULE_ASSET_PATH": str(medical_rules_path),
                "V31_MEDICAL_RULE_ASSET_CHECKSUM": medical_rules["content_checksum"],
                "V31_MEDICAL_RULE_VERSION": "medical-rules-v3.1-r1",
                "V31_MUSIC_GENERATION_RULES_PATH": str(rules_path),
                "V31_MUSIC_GENERATION_RULES_VERSION": music_rules["asset_version"],
                "V31_MUSIC_GENERATION_RULES_CHECKSUM": music_rules["content_checksum"],
            }
        )


def test_v31_real_rag_factory_loads_approved_corpus_before_returning_store(
    tmp_path, monkeypatch
):
    import json

    from backend.ai_engine.v3.rag_ingestion import _content_checksum
    from backend.ai_engine.v3.rag_store import VersionedRagStore
    from backend.app.core import agent_config
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
        "chunk_id": "chunk_001",
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
    chunk_payload["content_checksum"] = _content_checksum(
        chunk_payload, "content_checksum"
    )
    chunk = KnowledgeChunk(**chunk_payload)
    manifest_path = tmp_path / "manifest.json"
    chunks_path = tmp_path / "chunks.json"
    manifest_path.write_text(json.dumps(manifest.model_dump(mode="json")), encoding="utf-8")
    chunks_path.write_text(
        json.dumps([chunk.model_dump(mode="json")]),
        encoding="utf-8",
    )
    captured = {}

    monkeypatch.setattr(
        agent_config,
        "get_v31_embedding_provider",
        lambda environment: object(),
    )

    def capture_ingest(self, checked_manifest, checked_chunks):
        captured["manifest"] = checked_manifest
        captured["chunks"] = checked_chunks
        return "harmony_v31_medical_v3_1"

    monkeypatch.setattr(VersionedRagStore, "ingest", capture_ingest)
    fake_client = object()

    store = agent_config.get_v31_rag_store(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "QWEN_MODEL": "qwen-approved",
            "CHROMA_PERSIST_DIRECTORY": str(tmp_path / "chroma"),
            "CHROMA_COLLECTION": "harmony_v31",
            "RAG_CORPUS_MANIFEST_PATH": str(manifest_path),
            "RAG_CORPUS_CHUNKS_PATH": str(chunks_path),
        },
        client=fake_client,
    )
    store_again = agent_config.get_v31_rag_store(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "DASHSCOPE_API_KEY": "configured-value",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "QWEN_MODEL": "qwen-approved",
            "CHROMA_PERSIST_DIRECTORY": str(tmp_path / "chroma"),
            "CHROMA_COLLECTION": "harmony_v31",
            "RAG_CORPUS_MANIFEST_PATH": str(manifest_path),
            "RAG_CORPUS_CHUNKS_PATH": str(chunks_path),
        },
        client=fake_client,
    )

    assert isinstance(store, VersionedRagStore)
    assert store_again is store
    assert captured["manifest"].manifest_checksum == manifest.manifest_checksum
    assert [item.chunk_id for item in captured["chunks"]] == ["chunk_001"]

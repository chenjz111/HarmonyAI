def test_v31_provider_config_requires_explicit_real_mode_configuration():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "EMBEDDING_PROVIDER": "aliyun",
            "EMBEDDING_BASE_URL": "https://embedding.example",
            "EMBEDDING_API_KEY": "embedding-secret",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1024",
            "CHROMA_PERSIST_DIRECTORY": "data/chroma",
            "CHROMA_COLLECTION": "harmony_v31",
            "QWEN_BASE_URL": "https://qwen.example/v1",
            "QWEN_API_KEY": "qwen-secret",
            "QWEN_MODEL": "qwen-approved",
        }
    )

    assert config.real_agents is True
    assert config.embedding_dimension == 1024
    assert config.embedding_model == "text-embedding-v4"
    assert config.chroma_collection == "harmony_v31"
    assert config.safe_dict()["embedding_configured"] is True
    assert "embedding-secret" not in str(config.safe_dict())
    assert "qwen-secret" not in str(config.safe_dict())


def test_v31_provider_config_reports_missing_real_embedding_as_not_ready():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {"HARMONYAI_REAL_AGENTS": "true", "EMBEDDING_DIMENSION": "1024"}
    )

    assert config.real_agents is True
    assert config.readiness_error == "EMBEDDING_PROVIDER_NOT_CONFIGURED"


def test_v31_provider_config_rejects_hash_embedding_in_real_mode():
    from backend.ai_engine.v3.provider_config import V31ProviderConfig

    config = V31ProviderConfig.from_environment(
        {
            "HARMONYAI_REAL_AGENTS": "true",
            "EMBEDDING_PROVIDER": "local",
            "EMBEDDING_BASE_URL": "http://embedding.example",
            "EMBEDDING_API_KEY": "secret",
            "EMBEDDING_MODEL": "hash-v1",
            "EMBEDDING_DIMENSION": "64",
        }
    )

    assert config.readiness_error == "PRODUCTION_EMBEDDING_NOT_APPROVED"


def test_agent_config_exposes_v31_embedding_provider_from_explicit_environment():
    from backend.app.core.agent_config import get_v31_embedding_provider

    provider = get_v31_embedding_provider(
        {
            "EMBEDDING_BASE_URL": "https://embedding.example",
            "EMBEDDING_API_KEY": "secret",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1024",
        }
    )

    assert provider is not None
    assert provider.model == "text-embedding-v4"
    assert provider.dimension == 1024

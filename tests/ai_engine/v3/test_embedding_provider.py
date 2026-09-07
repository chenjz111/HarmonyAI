import json
from urllib.error import HTTPError

import asyncio
import pytest


def test_embedding_provider_sends_query_input_and_enforces_1024_dimensions():
    from backend.ai_engine.v3.embedding_provider import EmbeddingProvider

    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, headers, json.loads(body), timeout))
        return json.dumps(
            {
                "data": [{"embedding": [0.25] * 1024}],
                "model": "text-embedding-v4",
            }
        ).encode("utf-8")

    provider = EmbeddingProvider(
        base_url="https://embedding.example/v1",
        api_key="secret-key",
        model="text-embedding-v4",
        dimension=1024,
        transport=transport,
    )

    vector = provider.embed("approved query", input_type="query")

    assert len(vector) == 1024
    assert calls[0][0] == "https://embedding.example/v1/embeddings"
    assert calls[0][2]["input"] == "approved query"
    assert calls[0][2]["input_type"] == "query"
    assert calls[0][2]["model"] == "text-embedding-v4"


def test_embedding_provider_distinguishes_document_input_type():
    from backend.ai_engine.v3.embedding_provider import EmbeddingProvider

    bodies = []

    def transport(url, headers, body, timeout):
        bodies.append(json.loads(body))
        return json.dumps({"data": [{"embedding": [0.1] * 1024}]}).encode()

    provider = EmbeddingProvider(
        base_url="https://embedding.example",
        api_key="secret-key",
        model="text-embedding-v4",
        dimension=1024,
        transport=transport,
    )

    provider.embed("approved document", input_type="document")

    assert bodies[0]["input_type"] == "document"


def test_embedding_provider_rejects_wrong_dimension_without_returning_vector():
    from backend.ai_engine.v3.embedding_provider import (
        EmbeddingProvider,
        EmbeddingProviderFailure,
    )

    def transport(url, headers, body, timeout):
        return json.dumps({"data": [{"embedding": [0.1] * 3}]}).encode()

    provider = EmbeddingProvider(
        base_url="https://embedding.example",
        api_key="secret-key",
        model="text-embedding-v4",
        dimension=1024,
        transport=transport,
    )

    with pytest.raises(EmbeddingProviderFailure, match="EMBEDDING_DIMENSION_INVALID"):
        provider.embed("approved document", input_type="document")


def test_embedding_provider_maps_auth_failure_to_safe_error():
    from backend.ai_engine.v3.embedding_provider import (
        EmbeddingProvider,
        EmbeddingProviderFailure,
    )

    def transport(url, headers, body, timeout):
        raise HTTPError(url, 401, "unauthorized", {}, None)

    provider = EmbeddingProvider(
        base_url="https://embedding.example",
        api_key="secret-key",
        model="text-embedding-v4",
        dimension=1024,
        transport=transport,
    )

    with pytest.raises(EmbeddingProviderFailure) as caught:
        provider.embed("private user text", input_type="query")

    assert caught.value.error_code == "EMBEDDING_AUTH_FAILED"
    assert "private user text" not in str(caught.value)
    assert "secret-key" not in str(caught.value)


def test_async_embedding_provider_uses_same_contract():
    from backend.ai_engine.v3.embedding_provider import AsyncEmbeddingProvider

    calls = []

    def transport(url, headers, body, timeout):
        calls.append(json.loads(body))
        return json.dumps({"data": [{"embedding": [0.2] * 1024}]}).encode()

    provider = AsyncEmbeddingProvider(
        base_url="https://embedding.example",
        api_key="secret-key",
        model="text-embedding-v4",
        dimension=1024,
        transport=transport,
    )

    vector = asyncio.run(provider.aembed("approved query", input_type="query"))

    assert len(vector) == 1024
    assert calls[0]["input_type"] == "query"


def test_embedding_provider_propagates_dashscope_workspace_header():
    from backend.ai_engine.v3.embedding_provider import EmbeddingProvider

    headers_seen = []

    def transport(url, headers, body, timeout):
        del url, timeout
        headers_seen.append(headers)
        json.loads(body)
        return json.dumps({"data": [{"embedding": [0.2] * 1024}]}).encode()

    provider = EmbeddingProvider(
        base_url="https://dashscope.example/compatible-mode/v1",
        api_key="configured",
        workspace_id="workspace-test",
        model="text-embedding-v4",
        dimension=1024,
        transport=transport,
    )

    provider.embed("approved query", input_type="query")

    assert headers_seen[0]["X-DashScope-WorkSpace"] == "workspace-test"


def test_embedding_provider_factory_uses_dashscope_environment():
    from backend.ai_engine.v3.embedding_provider import embedding_provider_from_environment

    provider = embedding_provider_from_environment(
        {
            "DASHSCOPE_API_KEY": "configured",
            "DASHSCOPE_WORKSPACE_ID": "workspace-test",
            "DASHSCOPE_BASE_URL": "https://dashscope.example/compatible-mode/v1",
        }
    )

    assert provider is not None
    assert provider.model == "text-embedding-v4"
    assert provider.dimension == 1024
    assert provider.workspace_id == "workspace-test"

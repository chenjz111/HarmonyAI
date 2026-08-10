import json

import pytest

from backend.ai_engine.sprint4_contracts import ProviderError, ProviderRequest


@pytest.mark.asyncio
async def test_mock_provider_returns_metadata_and_records_call():
    from backend.ai_engine.providers import MockProvider

    provider = MockProvider({"items": []})
    response = await provider.complete_json(
        ProviderRequest(
            system_prompt="system",
            user_prompt="user",
            operation="narrative_extraction",
            prompt_version="assessment_v2.1",
        )
    )

    assert response.data == {"items": []}
    assert response.attempts == 1
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_async_qwen_provider_returns_json_and_usage_metadata():
    from backend.ai_engine.providers import AsyncQwenCompatibleProvider

    calls = []

    def transport(url, headers, body, timeout):
        calls.append((url, headers, json.loads(body), timeout))
        return json.dumps(
            {
                "choices": [{"message": {"content": "{\"items\": []}"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            }
        ).encode("utf-8")

    provider = AsyncQwenCompatibleProvider(
        base_url="https://qwen.example",
        api_key="test-key",
        model="qwen-test",
        transport=transport,
    )
    response = await provider.complete_json(
        ProviderRequest("system", "user", "narrative_extraction", "assessment_v2.1")
    )

    assert response.data == {"items": []}
    assert response.input_tokens == 11
    assert response.output_tokens == 7
    assert response.attempts == 1
    assert calls[0][0] == "https://qwen.example/chat/completions"
    assert calls[0][1]["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_async_qwen_timeout_is_retried_once_and_classified():
    from backend.ai_engine.providers import AsyncQwenCompatibleProvider

    calls = 0

    def transport(url, headers, body, timeout):
        del url, headers, body, timeout
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")

    provider = AsyncQwenCompatibleProvider(
        base_url="https://qwen.example",
        api_key="test-key",
        model="qwen-test",
        transport=transport,
    )
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete_json(
            ProviderRequest("system", "user", "narrative_extraction", "assessment_v2.1")
        )

    assert exc_info.value.reason_code == "TIMEOUT"
    assert calls == 2

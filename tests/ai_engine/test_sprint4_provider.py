import json
from urllib.error import HTTPError

import pytest

from backend.ai_engine.sprint4_contracts import ProviderError, ProviderErrorCode, ProviderRequest


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

    assert exc_info.value.reason_code == "READ_TIMEOUT"
    assert calls == 3


def test_sync_and_async_qwen_methods_share_json_repair_and_schema_validation():
    from backend.ai_engine.providers import AsyncQwenCompatibleProvider, QwenCompatibleProvider

    responses = iter([
        b'{"choices":[{"message":{"content":"```json\\n{\\"items\\": []}\\n```"}}]}',
        b'{"choices":[{"message":{"content":"prefix {\\"items\\": []} suffix"}}]}',
    ])

    def transport(url, headers, body, timeout):
        del url, headers, body, timeout
        return next(responses)

    sync = QwenCompatibleProvider(
        base_url="https://qwen.example",
        api_key="test-key",
        model="qwen-test",
        transport=transport,
        response_schema={"required": ["items"]},
    )
    assert sync.complete_json("system", "user") == {"items": []}

    async_provider = AsyncQwenCompatibleProvider(
        base_url="https://qwen.example",
        api_key="test-key",
        model="qwen-test",
        transport=transport,
        response_schema={"required": ["items"]},
    )
    result = __import__("asyncio").run(async_provider.acomplete_json("system", "user"))
    assert result == {"items": []}


def test_provider_uses_frozen_error_codes_for_rate_limit_and_schema_failure():
    from backend.ai_engine.providers import QwenCompatibleProvider

    def rate_limited(url, headers, body, timeout):
        del url, headers, body, timeout
        raise HTTPError("https://qwen.example", 429, "rate limited", {}, None)

    provider = QwenCompatibleProvider(
        base_url="https://qwen.example",
        api_key="test-key",
        model="qwen-test",
        transport=rate_limited,
        max_retries=0,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.complete_json("system", "user")
    assert exc_info.value.reason_code == ProviderErrorCode.RATE_LIMITED


def test_async_provider_retries_rate_limit_twice_then_allows_third_attempt():
    from backend.ai_engine.providers import AsyncQwenCompatibleProvider

    calls = 0

    def transport(url, headers, body, timeout):
        del url, headers, body, timeout
        nonlocal calls
        calls += 1
        if calls < 3:
            raise HTTPError("https://qwen.example", 429, "rate limited", {}, None)
        return b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}'

    provider = AsyncQwenCompatibleProvider(
        base_url="https://qwen.example",
        api_key="test-key",
        model="qwen-test",
        transport=transport,
        max_retries=2,
    )
    result = __import__("asyncio").run(provider.acomplete_json("system", "user"))
    assert result == {"ok": True}
    assert calls == 3


def test_provider_log_fields_strip_all_user_text_and_prompts():
    from backend.ai_engine.providers import build_provider_log_fields

    fields = build_provider_log_fields(
        request_id="req-1",
        session_id="session-1",
        agent_id="assessment_agent",
        source_type="narrative",
        text_length=42,
        provider="qwen",
        model="qwen-test",
        prompt_version="assessment_v2.1",
        latency_ms=10,
        input_tokens=3,
        output_tokens=2,
        status="success",
        error_code=None,
        retry_count=0,
        user_prompt="用户原文不得进入日志",
        system_prompt="系统 Prompt 不得进入日志",
    )

    assert fields == {
        "request_id": "req-1",
        "session_id": "session-1",
        "agent_id": "assessment_agent",
        "source_type": "narrative",
        "text_length": 42,
        "provider": "qwen",
        "model": "qwen-test",
        "prompt_version": "assessment_v2.1",
        "latency_ms": 10,
        "input_tokens": 3,
        "output_tokens": 2,
        "status": "success",
        "error_code": None,
        "retry_count": 0,
    }

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
import time
from collections.abc import Mapping
from typing import Any, Callable, Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .sprint4_contracts import ProviderError, ProviderErrorCode, ProviderRequest, ProviderResponse


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        ...


class JsonLLMProvider(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        ...


class AsyncJsonProvider(Protocol):
    async def complete_json(self, request: ProviderRequest) -> ProviderResponse:
        ...


class LLMProviderError(RuntimeError):
    pass


class ConnectionTimeoutError(TimeoutError):
    """Transport may use this to identify a TCP connection timeout."""


class ReadTimeoutError(TimeoutError):
    """Transport may use this to identify a response-read timeout."""


def _repair_json_content(content: Any) -> object:
    if not isinstance(content, str):
        raise ValueError("message content must be text")
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()

    candidates = [cleaned]
    starts = [index for index, char in enumerate(cleaned) if char in "{["]
    for start in starts:
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end >= start:
            candidates.append(cleaned[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Only repair a truncated object when the missing tail is unambiguous.
    if "{" in cleaned and "}" not in cleaned:
        try:
            return json.loads(cleaned + "}")
        except json.JSONDecodeError:
            pass
    raise ValueError("JSON repair failed")


def _validate_schema(value: object, schema: Mapping[str, object] | Callable[[object], None] | None) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("response must be a JSON object")
    if schema is None:
        return value
    if callable(schema):
        schema(value)
        return value
    if schema.get("type", "object") != "object":
        raise ValueError("only object response schemas are supported")
    required = schema.get("required", ())
    if not isinstance(required, (list, tuple)) or any(key not in value for key in required):
        raise ValueError("response does not satisfy required schema fields")
    return value


class QwenCompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 20.0,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        max_retries: int = 2,
        transport: Callable[[str, dict[str, str], bytes, float], bytes] | None = None,
        response_schema: Mapping[str, object] | Callable[[object], None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.connect_timeout = connect_timeout if connect_timeout is not None else timeout
        self.read_timeout = read_timeout if read_timeout is not None else timeout
        self.timeout = self.read_timeout
        self.max_retries = max(0, min(3, max_retries))
        self.transport = transport or self._http_transport
        self.response_schema = response_schema

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        return self._complete_sync(system_prompt, user_prompt)

    async def acomplete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        return (await self._complete_async(system_prompt, user_prompt)).data

    def _request_body(self, system_prompt: str, user_prompt: str) -> tuple[str, dict[str, str], bytes]:
        if not self.base_url or not self.api_key or not self.model:
            raise ProviderError(
                ProviderErrorCode.NOT_CONFIGURED,
                False,
                "Qwen Provider 未配置。",
            )
        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return (
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            body,
        )

    def _parse_raw(self, raw: bytes) -> tuple[dict[str, object], int | None, int | None]:
        if not raw:
            raise _ProviderFailure(ProviderErrorCode.EMPTY_RESPONSE, False, "Provider 返回为空。")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _ProviderFailure(ProviderErrorCode.INVALID_JSON, False, "Provider 返回不是有效 JSON。", exc) from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise _ProviderFailure(ProviderErrorCode.INVALID_RESPONSE, False, "Provider 返回结构不完整。", exc) from exc
        try:
            parsed = _repair_json_content(content)
        except (TypeError, ValueError) as exc:
            raise _ProviderFailure(ProviderErrorCode.JSON_REPAIR_FAILED, False, "Provider JSON 修复失败。", exc) from exc
        try:
            result = _validate_schema(parsed, self.response_schema)
        except (TypeError, ValueError) as exc:
            raise _ProviderFailure(ProviderErrorCode.SCHEMA_VIOLATION, False, "Provider 返回不符合 Schema。", exc) from exc
        usage = payload.get("usage", {})
        return result, _token_count(usage, "prompt_tokens"), _token_count(usage, "completion_tokens")

    def _complete_sync(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        url, headers, body = self._request_body(system_prompt, user_prompt)
        started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            try:
                raw = self.transport(url, headers, body, self.read_timeout)
                result, _, _ = self._parse_raw(raw)
                return result
            except ProviderError:
                raise
            except BaseException as exc:
                failure = self._classify(exc)
                if not self._should_retry(failure.code, attempt):
                    raise self._public_error(failure, attempt, started) from exc
                self._backoff(failure.code, attempt)
        raise AssertionError("provider retry loop exhausted")

    async def _complete_async(self, system_prompt: str, user_prompt: str) -> "_Completion":
        url, headers, body = self._request_body(system_prompt, user_prompt)
        started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            try:
                raw = await asyncio.to_thread(self.transport, url, headers, body, self.read_timeout)
                result, input_tokens, output_tokens = self._parse_raw(raw)
                return _Completion(result, input_tokens, output_tokens, attempt + 1)
            except ProviderError:
                raise
            except BaseException as exc:
                failure = self._classify(exc)
                if not self._should_retry(failure.code, attempt):
                    raise self._public_error(failure, attempt, started) from exc
                await asyncio.sleep(self._backoff_seconds(failure.code, attempt))
        raise AssertionError("provider retry loop exhausted")

    def _classify(self, exc: BaseException) -> "_ProviderFailure":
        if isinstance(exc, HTTPError):
            if exc.code == 429:
                return _ProviderFailure(ProviderErrorCode.RATE_LIMITED, True, "请求频率受限，请稍后重试。", exc)
            if 500 <= exc.code <= 599:
                return _ProviderFailure(ProviderErrorCode.SERVER_ERROR, True, "Provider 服务暂时不可用。", exc)
            return _ProviderFailure(ProviderErrorCode.INVALID_RESPONSE, False, "Provider 请求失败。", exc)
        if isinstance(exc, ConnectionTimeoutError):
            return _ProviderFailure(ProviderErrorCode.CONNECTION_TIMEOUT, True, "连接 Provider 超时。", exc)
        if isinstance(exc, ReadTimeoutError):
            return _ProviderFailure(ProviderErrorCode.READ_TIMEOUT, True, "读取 Provider 响应超时。", exc)
        if isinstance(exc, TimeoutError):
            return _ProviderFailure(ProviderErrorCode.READ_TIMEOUT, True, "读取 Provider 响应超时。", exc)
        if isinstance(exc, OSError):
            return _ProviderFailure(ProviderErrorCode.INVALID_RESPONSE, True, "Provider 网络请求失败。", exc)
        return _ProviderFailure(ProviderErrorCode.INVALID_RESPONSE, False, "Provider 请求失败。", exc)

    def _should_retry(self, code: ProviderErrorCode, attempt: int) -> bool:
        return attempt < self.max_retries and code in {
            ProviderErrorCode.RATE_LIMITED,
            ProviderErrorCode.SERVER_ERROR,
            ProviderErrorCode.CONNECTION_TIMEOUT,
            ProviderErrorCode.READ_TIMEOUT,
        }

    def _backoff_seconds(self, code: ProviderErrorCode, attempt: int) -> float:
        if code == ProviderErrorCode.RATE_LIMITED:
            return float(2 ** attempt)
        if code == ProviderErrorCode.SERVER_ERROR:
            return 1.0
        return 0.0

    def _backoff(self, code: ProviderErrorCode, attempt: int) -> None:
        delay = self._backoff_seconds(code, attempt)
        if delay:
            time.sleep(delay)

    def _public_error(self, failure: "_ProviderFailure", attempt: int, started: float) -> ProviderError:
        error = ProviderError(failure.code, self._should_retry(failure.code, attempt), failure.message, cause=failure.cause)
        error.retry_count = attempt
        error.latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return error

    @staticmethod
    def _http_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> bytes:
        request = Request(url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=timeout) as response:
            return response.read()


@dataclass(frozen=True)
class _ProviderFailure:
    code: ProviderErrorCode
    retryable: bool
    message: str
    cause: BaseException | None = None


@dataclass(frozen=True)
class _Completion:
    data: dict[str, object]
    input_tokens: int | None
    output_tokens: int | None
    attempts: int


class AsyncQwenCompatibleProvider(QwenCompatibleProvider):
    """Compatibility wrapper for the pre-freeze request-object call site."""

    async def complete_json(self, request: ProviderRequest) -> ProviderResponse:
        started = time.perf_counter()
        completion = await self._complete_async(request.system_prompt, request.user_prompt)
        return ProviderResponse(
            data=completion.data,
            provider="qwen",
            model=self.model,
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            attempts=completion.attempts,
        )


class MockProvider:
    def __init__(self, response: dict[str, object] | None = None, *, error: ProviderError | None = None, responses: dict[str, dict] | None = None) -> None:
        self.response = dict(response or {})
        self.responses = responses or {}
        self.error = error
        self.calls = 0

    def complete_json(self, system_prompt: str | ProviderRequest, user_prompt: str | None = None) -> Any:
        if isinstance(system_prompt, ProviderRequest):
            async def legacy_result() -> ProviderResponse:
                data = await self.acomplete_json(system_prompt.system_prompt, system_prompt.user_prompt)
                return ProviderResponse(data, "mock", "mock", 0, 0, 0, 1)
            return legacy_result()
        key = system_prompt + "\n" + (user_prompt or "")
        return dict(self.responses.get(key, self.response))

    async def acomplete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.complete_json(system_prompt, user_prompt)

    async def complete_json_async(self, request: ProviderRequest) -> ProviderResponse:
        data = await self.acomplete_json(request.system_prompt, request.user_prompt)
        return ProviderResponse(data, "mock", "mock", 0, 0, 0, 1)

    @staticmethod
    def from_jsonl(path: str) -> "MockProvider":
        responses: dict[str, dict] = {}
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                responses[str(row["prompt_hash"])] = dict(row["response"])
        return MockProvider(responses=responses)


class SyncJsonProviderAdapter:
    def __init__(self, provider: Any) -> None:
        self.provider = provider

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        result = self.provider.complete_json(system_prompt, user_prompt)
        if isinstance(result, dict):
            return result
        return asyncio.run(self.provider.acomplete_json(system_prompt, user_prompt))


def build_provider_log_fields(
    *,
    request_id: str,
    session_id: str,
    agent_id: str,
    source_type: str,
    text_length: int,
    provider: str,
    model: str,
    prompt_version: str,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    status: str,
    error_code: str | None,
    retry_count: int,
    user_prompt: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, object]:
    del user_prompt, system_prompt
    return {
        "request_id": request_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "source_type": source_type,
        "text_length": text_length,
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "status": status,
        "error_code": error_code,
        "retry_count": retry_count,
    }


def _token_count(usage: object, key: str) -> int | None:
    if not isinstance(usage, Mapping):
        return None
    value = usage.get(key)
    return value if type(value) is int and value >= 0 else None


def qwen_provider_from_env() -> QwenCompatibleProvider | None:
    base_url = os.getenv("QWEN_BASE_URL", "").strip()
    api_key = os.getenv("QWEN_API_KEY", "").strip()
    model = os.getenv("QWEN_MODEL", "").strip()
    if not all((base_url, api_key, model)):
        return None
    return QwenCompatibleProvider(base_url=base_url, api_key=api_key, model=model)


def async_qwen_provider_from_env() -> AsyncQwenCompatibleProvider | None:
    """Return the request-object provider used by Sprint 4 extraction."""
    base_url = os.getenv("QWEN_BASE_URL", "").strip()
    api_key = os.getenv("QWEN_API_KEY", "").strip()
    model = os.getenv("QWEN_MODEL", "").strip()
    if not all((base_url, api_key, model)):
        return None
    return AsyncQwenCompatibleProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )


@dataclass(frozen=True)
class KnowledgeHit:
    text: str
    metadata: dict[str, object]
    score: float
    distance: float | None = None


class VectorStore(Protocol):
    def search(self, query: str, limit: int = 5) -> list[KnowledgeHit]:
        ...


class FallbackLLMProvider:
    def complete(self, prompt: str) -> str:
        del prompt
        return "规则引擎已生成保守建议；结果仅供参考，不构成医疗诊断或治疗建议。"


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._documents: list[tuple[str, dict[str, str]]] = []

    def add(self, text: str, metadata: Mapping[str, str]) -> None:
        self._documents.append((text, dict(metadata)))

    def search(self, query: str, limit: int = 5) -> list[KnowledgeHit]:
        if not query.strip() or limit <= 0:
            return []
        query_tokens = set(query.replace("，", " ").split())
        if len(query_tokens) == 1:
            query_tokens.update(query_tokens.pop())
        hits = []
        for text, metadata in self._documents:
            score = len(query_tokens.intersection(set(text))) / max(len(query_tokens), 1)
            if score > 0:
                hits.append(KnowledgeHit(text, metadata, score))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

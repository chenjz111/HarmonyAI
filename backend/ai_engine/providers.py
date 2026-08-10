from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
import time
from typing import Any, Callable
from typing import Mapping, Protocol
from urllib.request import Request, urlopen

from .sprint4_contracts import (
    ProviderError,
    ProviderRequest,
    ProviderResponse,
)


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


class QwenCompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        transport: Callable[[str, dict[str, str], bytes, float], bytes] | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.transport = transport or self._http_transport
        self.timeout = timeout

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        if not self.base_url or not self.api_key or not self.model:
            raise LLMProviderError("Qwen-compatible provider is not configured")

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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            raw = self.transport(f"{self.base_url}/chat/completions", headers, body, self.timeout)
            payload = json.loads(raw.decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            parsed = self._parse_json_content(content)
        except (KeyError, IndexError, TypeError, ValueError, OSError, LLMProviderError) as exc:
            raise LLMProviderError(f"Qwen-compatible response failed: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError("Qwen-compatible response must be a JSON object")
        return parsed

    @staticmethod
    def _parse_json_content(content: Any) -> object:
        if not isinstance(content, str):
            raise ValueError("message content must be text")
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").removeprefix("json").strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise ValueError("no JSON object found")
        return json.loads(cleaned[start : end + 1])

    @staticmethod
    def _http_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> bytes:
        request = Request(url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=timeout) as response:
            return response.read()


class AsyncQwenCompatibleProvider:
    """Async Qwen-compatible gateway with bounded retries and typed failures."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        transport: Callable[[str, dict[str, str], bytes, float], bytes] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.transport = transport or QwenCompatibleProvider._http_transport

    async def complete_json(self, request: ProviderRequest) -> ProviderResponse:
        if not self.base_url or not self.api_key or not self.model:
            raise ProviderError(
                "NOT_CONFIGURED",
                False,
                "Qwen Provider 未配置。",
            )

        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        attempts = 0
        while attempts < 2:
            attempts += 1
            try:
                raw = await asyncio.to_thread(
                    self.transport,
                    f"{self.base_url}/chat/completions",
                    headers,
                    body,
                    request.timeout_seconds,
                )
                payload = json.loads(raw.decode("utf-8"))
                content = payload["choices"][0]["message"]["content"]
                parsed = QwenCompatibleProvider._parse_json_content(content)
                if not isinstance(parsed, dict):
                    raise ValueError("response must be a JSON object")
                usage = payload.get("usage", {})
                return ProviderResponse(
                    data=parsed,
                    provider="qwen",
                    model=self.model,
                    latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
                    input_tokens=_token_count(usage, "prompt_tokens"),
                    output_tokens=_token_count(usage, "completion_tokens"),
                    attempts=attempts,
                )
            except TimeoutError as exc:
                if attempts < 2:
                    continue
                raise ProviderError(
                    "TIMEOUT",
                    True,
                    "文本分析超时，请稍后重试。",
                    cause=exc,
                ) from exc
            except OSError as exc:
                if attempts < 2:
                    continue
                raise ProviderError(
                    "NETWORK",
                    True,
                    "文本分析服务暂时不可用。",
                    cause=exc,
                ) from exc
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    "INVALID_JSON",
                    False,
                    "文本分析返回了无法解析的结果。",
                    cause=exc,
                ) from exc
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderError(
                    "SCHEMA_ERROR",
                    False,
                    "文本分析返回了不完整的结果。",
                    cause=exc,
                ) from exc

        raise ProviderError("NETWORK", True, "文本分析服务暂时不可用。")


class MockProvider:
    """Deterministic async Provider for tests and offline evaluation."""

    def __init__(
        self,
        response: dict[str, object] | None = None,
        *,
        error: ProviderError | None = None,
    ) -> None:
        self.response = dict(response or {})
        self.error = error
        self.calls = 0

    async def complete_json(self, request: ProviderRequest) -> ProviderResponse:
        del request
        attempts = 0
        while attempts < 2:
            attempts += 1
            self.calls += 1
            if self.error is None:
                return ProviderResponse(
                    data=dict(self.response),
                    provider="mock",
                    model="mock",
                    latency_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    attempts=attempts,
                )
            if not self.error.retryable or attempts == 2:
                raise self.error
        raise self.error


class SyncJsonProviderAdapter:
    """Named bridge for legacy synchronous V2.0/V2.1 call sites."""

    def __init__(self, provider: AsyncJsonProvider) -> None:
        self.provider = provider

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        response = asyncio.run(
            self.provider.complete_json(
                ProviderRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    operation="legacy_json_completion",
                    prompt_version="legacy",
                )
            )
        )
        return response.data


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

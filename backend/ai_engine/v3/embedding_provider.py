"""Approved V3.1 embedding Provider boundary.

The production embedding is selected by configuration and is deliberately
separate from the legacy ``hash-v1`` demo embedding. This module does not
log input text or credentials.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
import json
import time
from typing import Literal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

EmbeddingInputType = Literal["query", "document"]
Transport = Callable[[str, dict[str, str], bytes, float], bytes]


class EmbeddingProviderFailure(RuntimeError):
    """Stable, safe embedding failure without raw request data."""

    def __init__(
        self,
        error_code: str,
        *,
        retryable: bool,
        safe_message: str,
        cause: BaseException | None = None,
    ) -> None:
        self.error_code = error_code
        self.retryable = retryable
        self.safe_message = safe_message
        self.cause = cause
        super().__init__(f"{error_code}: {safe_message}")


class EmbeddingProvider:
    """Synchronous OpenAI-compatible embedding adapter with dimension gates."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int,
        timeout: float = 20.0,
        max_retries: int = 2,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimension = dimension
        self.timeout = timeout
        self.max_retries = max(0, min(3, max_retries))
        self.transport = transport or self._http_transport

    def embed(
        self,
        text: str,
        *,
        input_type: EmbeddingInputType,
    ) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingProviderFailure(
                "EMBEDDING_INPUT_EMPTY",
                retryable=False,
                safe_message="Embedding 输入不能为空。",
            )
        if input_type not in {"query", "document"}:
            raise EmbeddingProviderFailure(
                "EMBEDDING_INPUT_TYPE_INVALID",
                retryable=False,
                safe_message="Embedding 输入类型无效。",
            )
        if not self.base_url or not self.api_key or not self.model:
            raise EmbeddingProviderFailure(
                "EMBEDDING_PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="Embedding 服务尚未配置。",
            )
        if self.dimension <= 0:
            raise EmbeddingProviderFailure(
                "EMBEDDING_DIMENSION_INVALID",
                retryable=False,
                safe_message="Embedding 维度配置无效。",
            )

        body = json.dumps(
            {
                "model": self.model,
                "input": text,
                "input_type": input_type,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/embeddings"
        started = time.perf_counter()
        del started  # reserved for the caller's provider audit metadata

        for attempt in range(self.max_retries + 1):
            try:
                raw = self.transport(url, headers, body, self.timeout)
                vector = self._parse_vector(raw)
                if len(vector) != self.dimension:
                    raise EmbeddingProviderFailure(
                        "EMBEDDING_DIMENSION_INVALID",
                        retryable=False,
                        safe_message="Embedding 返回维度与配置不一致。",
                    )
                return vector
            except EmbeddingProviderFailure:
                raise
            except HTTPError as error:
                failure = self._http_failure(error)
            except TimeoutError as error:
                failure = EmbeddingProviderFailure(
                    "EMBEDDING_TIMEOUT",
                    retryable=True,
                    safe_message="Embedding 服务响应超时。",
                    cause=error,
                )
            except (OSError, json.JSONDecodeError, TypeError, KeyError, IndexError, ValueError) as error:
                failure = EmbeddingProviderFailure(
                    "EMBEDDING_INVALID_RESPONSE",
                    retryable=True,
                    safe_message="Embedding 服务返回无效结果。",
                    cause=error,
                )
            if not failure.retryable or attempt >= self.max_retries:
                raise failure from None

        raise AssertionError("embedding retry loop exhausted")

    @staticmethod
    def _parse_vector(raw: bytes) -> list[float]:
        if not raw:
            raise EmbeddingProviderFailure(
                "EMBEDDING_EMPTY_RESPONSE",
                retryable=False,
                safe_message="Embedding 服务返回为空。",
            )
        payload = json.loads(raw.decode("utf-8"))
        vector = payload["data"][0]["embedding"]
        if not isinstance(vector, list) or not vector:
            raise EmbeddingProviderFailure(
                "EMBEDDING_INVALID_RESPONSE",
                retryable=False,
                safe_message="Embedding 服务返回无效结果。",
            )
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in vector):
            raise EmbeddingProviderFailure(
                "EMBEDDING_INVALID_RESPONSE",
                retryable=False,
                safe_message="Embedding 服务返回无效结果。",
            )
        return [float(value) for value in vector]

    @staticmethod
    def _http_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> bytes:
        request = Request(url, data=body, headers=headers, method="POST")
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    @staticmethod
    def _http_failure(error: HTTPError) -> EmbeddingProviderFailure:
        if error.code in {401, 403}:
            return EmbeddingProviderFailure(
                "EMBEDDING_AUTH_FAILED",
                retryable=False,
                safe_message="Embedding 服务认证失败。",
                cause=error,
            )
        if error.code == 429:
            return EmbeddingProviderFailure(
                "EMBEDDING_RATE_LIMITED",
                retryable=True,
                safe_message="Embedding 服务请求频率受限。",
                cause=error,
            )
        if 500 <= error.code <= 599:
            return EmbeddingProviderFailure(
                "EMBEDDING_UNAVAILABLE",
                retryable=True,
                safe_message="Embedding 服务暂时不可用。",
                cause=error,
            )
        return EmbeddingProviderFailure(
            "EMBEDDING_INVALID_RESPONSE",
            retryable=False,
            safe_message="Embedding 请求失败。",
            cause=error,
        )


class AsyncEmbeddingProvider(EmbeddingProvider):
    """Async facade sharing the exact sync validation and failure contract."""

    async def aembed(
        self,
        text: str,
        *,
        input_type: EmbeddingInputType,
    ) -> list[float]:
        return await asyncio.to_thread(self.embed, text, input_type=input_type)


def embedding_provider_from_environment(
    environment: Mapping[str, str],
) -> EmbeddingProvider | None:
    """Build the approved provider only when all required values are present."""

    base_url = environment.get("EMBEDDING_BASE_URL", "").strip()
    api_key = environment.get("EMBEDDING_API_KEY", "").strip()
    model = environment.get("EMBEDDING_MODEL", "").strip()
    dimension = _parse_dimension(environment.get("EMBEDDING_DIMENSION", "1024"))
    if not all((base_url, api_key, model)) or dimension is None:
        return None
    return EmbeddingProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        dimension=dimension,
    )


def _parse_dimension(value: str) -> int | None:
    try:
        dimension = int(value)
    except (TypeError, ValueError):
        return None
    return dimension if dimension > 0 else None

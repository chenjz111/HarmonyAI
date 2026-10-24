"""V3.1 real-provider configuration and readiness gates."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True)
class V31ProviderConfig:
    real_agents: bool
    embedding_provider: str | None
    embedding_base_url: str | None
    embedding_api_key: str | None
    embedding_model: str | None
    embedding_dimension: int
    chroma_persist_directory: str | None
    chroma_collection: str | None
    qwen_base_url: str | None
    qwen_api_key: str | None
    qwen_model: str | None
    dashscope_workspace_id: str | None = None
    readiness_error: str | None = None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "V31ProviderConfig":
        real_agents = environment.get("HARMONYAI_REAL_AGENTS", "").strip().lower() in {
            "true",
            "1",
            "yes",
        }
        dimension = _parse_int(environment.get("EMBEDDING_DIMENSION", "1024"))
        dashscope_key = _value(environment, "DASHSCOPE_API_KEY")
        workspace_id = _value(environment, "DASHSCOPE_WORKSPACE_ID")
        dashscope_base_url = _value(environment, "DASHSCOPE_BASE_URL") or (
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
            if dashscope_key
            else None
        )
        embedding_model = _value(environment, "EMBEDDING_MODEL") or (
            "text-embedding-v4" if dashscope_key else None
        )
        embedding_provider = _value(environment, "EMBEDDING_PROVIDER") or (
            "dashscope" if dashscope_key else None
        )
        embedding_base_url = _value(environment, "EMBEDDING_BASE_URL") or dashscope_base_url
        embedding_api_key = _value(environment, "EMBEDDING_API_KEY") or dashscope_key
        qwen_base_url = _value(environment, "QWEN_BASE_URL") or dashscope_base_url
        qwen_api_key = _value(environment, "QWEN_API_KEY") or dashscope_key
        qwen_model = _value(environment, "QWEN_MODEL") or _value(
            environment, "DASHSCOPE_QWEN_MODEL"
        )
        readiness_error = None
        if real_agents:
            if not dashscope_key or not workspace_id:
                readiness_error = "DASHSCOPE_PROVIDER_NOT_CONFIGURED"
            elif dimension is None:
                readiness_error = "EMBEDDING_DIMENSION_INVALID"
            elif not all(
                (embedding_provider, embedding_base_url, embedding_api_key, embedding_model)
            ):
                readiness_error = "EMBEDDING_PROVIDER_NOT_CONFIGURED"
            elif embedding_model != "text-embedding-v4" or dimension != 1024:
                readiness_error = "PRODUCTION_EMBEDDING_NOT_APPROVED"
            elif not _value(environment, "CHROMA_PERSIST_DIRECTORY") or not _value(
                environment, "CHROMA_COLLECTION"
            ):
                readiness_error = "CHROMA_NOT_CONFIGURED"
            elif not all(
                (qwen_base_url, qwen_api_key, qwen_model)
            ):
                readiness_error = "QWEN_PROVIDER_NOT_CONFIGURED"

        return cls(
            real_agents=real_agents,
            embedding_provider=embedding_provider,
            embedding_base_url=embedding_base_url,
            embedding_api_key=embedding_api_key,
            embedding_model=embedding_model,
            embedding_dimension=dimension or 0,
            chroma_persist_directory=_value(environment, "CHROMA_PERSIST_DIRECTORY"),
            chroma_collection=_value(environment, "CHROMA_COLLECTION"),
            qwen_base_url=qwen_base_url,
            qwen_api_key=qwen_api_key,
            qwen_model=qwen_model,
            dashscope_workspace_id=workspace_id,
            readiness_error=readiness_error,
        )

    def safe_dict(self) -> dict[str, object]:
        """Return health/configuration facts without secrets or endpoints."""

        return {
            "real_agents": self.real_agents,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "embedding_configured": all(
                (
                    self.embedding_provider,
                    self.embedding_base_url,
                    self.embedding_api_key,
                    self.embedding_model,
                )
            ),
            "chroma_configured": bool(
                self.chroma_persist_directory and self.chroma_collection
            ),
            "qwen_configured": all(
                (self.qwen_base_url, self.qwen_api_key, self.qwen_model)
            ),
            "qwen_model": self.qwen_model,
            "dashscope_configured": bool(self.dashscope_workspace_id),
            "readiness_error": self.readiness_error,
        }


def _value(environment: Mapping[str, str], key: str) -> str | None:
    value = environment.get(key, "").strip()
    return value or None


def _parse_int(value: str) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None

"""Agent 4 music provider bundle — env-driven, secret-safe.

The concrete provider adapter is selected only after the music provider
Decision Record is approved (docs/sprint5/provider-decision-record-music.md).
Until then the default bundle surfaces a NotConfigured provider so generation
can degrade to reviewed local matching instead of pretending success.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.ai_engine.v3.music_provider import (
    MusicGenerationProvider,
    MusicProviderFailureV3,
)
from backend.app.schemas.v3.common import ProviderCapabilities, ProviderHealth
from backend.app.schemas.v3.music import (
    MusicProviderCapabilities,
    ProviderMusicRequest,
    ProviderTask,
)


class NotConfiguredMusicProvider:
    """Raises PROVIDER_NOT_CONFIGURED on every operation."""

    def __init__(self, provider_name: str = "unconfigured") -> None:
        self.provider_name = provider_name

    def _failure(self) -> MusicProviderFailureV3:
        return MusicProviderFailureV3(
            "PROVIDER_NOT_CONFIGURED",
            retryable=False,
            safe_message="音乐生成服务尚未配置。",
        )

    def create_task(self, request: ProviderMusicRequest) -> ProviderTask:
        del request
        raise self._failure()

    def get_task(self, provider_task_id: str) -> ProviderTask:
        del provider_task_id
        raise self._failure()

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        del provider_task_id
        raise self._failure()

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="not_configured",
            provider_kind="cloud",
            provider=self.provider_name,
            model=None,
            checked_at=datetime.now(timezone.utc),
            capabilities=ProviderCapabilities(
                structured_json=False,
                max_input_characters=1,
            ),
            safe_message="音乐生成服务尚未配置。",
        )

    def capabilities(self) -> MusicProviderCapabilities:
        return MusicProviderCapabilities(
            max_duration_seconds=1,
            supports_progress=False,
            supports_cancel=False,
            supported_instruments=["guqin"],
            supported_formats=["mp3"],
        )


@dataclass(frozen=True)
class MusicProviderBundle:
    provider: MusicGenerationProvider
    health: ProviderHealth


def build_music_provider_bundle(
    environment: Mapping[str, str],
) -> MusicProviderBundle:
    """Build the active music provider without logging or returning credentials."""

    name = environment.get("MUSIC_PROVIDER", "").strip()
    base_url = environment.get("MUSIC_PROVIDER_BASE_URL", "").strip()
    api_key = environment.get("MUSIC_PROVIDER_API_KEY", "").strip()
    model = environment.get("MUSIC_PROVIDER_MODEL", "").strip()
    if name and base_url and api_key and model:
        # TODO(owner): wire the concrete adapter once the provider Decision
        # Record is approved. A configured-but-unwired environment must never
        # fake generation success, so it still degrades to local matching.
        return MusicProviderBundle(
            provider=NotConfiguredMusicProvider(provider_name=name),
            health=ProviderHealth(
                status="not_configured",
                provider_kind="cloud",
                provider=name,
                model=model,
                checked_at=datetime.now(timezone.utc),
                capabilities=ProviderCapabilities(
                    structured_json=False,
                    max_input_characters=1,
                ),
                safe_message="音乐生成 Provider 适配器待接线。",
            ),
        )
    return MusicProviderBundle(
        provider=NotConfiguredMusicProvider(),
        health=ProviderHealth(
            status="not_configured",
            provider_kind="cloud",
            provider="music",
            model=None,
            checked_at=datetime.now(timezone.utc),
            capabilities=ProviderCapabilities(
                structured_json=False,
                max_input_characters=1,
            ),
            safe_message="音乐生成服务尚未配置。",
        ),
    )

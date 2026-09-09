"""Agent 4 music provider bundle — env-driven, secret-safe.

The concrete provider is selected from deployment environment variables only.
``MUSIC_PROVIDER=minimax`` with complete configuration wires the MiniMax Music
adapter (backend/ai_engine/v3/minimax_music_provider.py). Any missing or
unknown configuration keeps the NotConfigured provider so generation degrades
to reviewed local matching or an explicit failure — never fake success and
never a silent switch to Mock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.ai_engine.v3.minimax_music_provider import (
    DEFAULT_MINIMAX_BASE_URL,
    MINIMAX_MODELS,
    MiniMaxMusicProvider,
)
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

    name = environment.get("MUSIC_PROVIDER", "").strip().lower()
    base_url = environment.get("MUSIC_PROVIDER_BASE_URL", "").strip()
    api_key = environment.get("MUSIC_PROVIDER_API_KEY", "").strip()
    model = environment.get("MUSIC_PROVIDER_MODEL", "").strip()

    if name == "minimax":
        if not api_key or not model or model not in MINIMAX_MODELS:
            # Fail closed: readiness stays not_configured until the Owner
            # provides a complete, valid MiniMax configuration.
            return MusicProviderBundle(
                provider=NotConfiguredMusicProvider(provider_name="minimax"),
                health=ProviderHealth(
                    status="not_configured",
                    provider_kind="cloud",
                    provider="minimax",
                    model=model or None,
                    checked_at=datetime.now(timezone.utc),
                    capabilities=ProviderCapabilities(
                        structured_json=False,
                        max_input_characters=1,
                    ),
                    safe_message=(
                        "MiniMax 音乐生成配置不完整（需要 API Key 与有效模型）。"
                        if model
                        else "MiniMax 音乐生成服务尚未配置。"
                    ),
                ),
            )
        provider = MiniMaxMusicProvider(
            base_url=base_url or DEFAULT_MINIMAX_BASE_URL,
            api_key=api_key,
            model=model,
            media_root=environment.get("HARMONY_MEDIA_ROOT") or None,
        )
        return MusicProviderBundle(
            provider=provider,
            health=provider.health(),
        )
    if name and base_url and api_key and model:
        # A configured-but-unwired provider name still degrades instead of
        # faking generation success (concrete wiring only exists for minimax).
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

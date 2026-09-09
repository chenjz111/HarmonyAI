"""Agent 4 music provider bundle — env-driven, secret-safe.

The concrete provider is selected from deployment environment variables only.
``MUSIC_PROVIDER=stability`` with a complete configuration wires the Stability
AI Stable Audio 2.5 adapter (backend/ai_engine/v3/stability_music_provider.py,
key read from ``STABILITY_API_KEY``).

MiniMax remains implemented for history (backend/ai_engine/v3/
minimax_music_provider.py) but is NOT an enabled real target for Sprint 5:
Owner real smoke returned HTTP 410 / provider code 2153
(``BLOCKED_BY_PROVIDER_ENTITLEMENT``), so a ``MUSIC_PROVIDER=minimax``
environment stays ``not_configured`` instead of pretending to work.

Any missing/unknown configuration keeps the NotConfigured provider so
generation degrades to reviewed local matching or an explicit failure — never
fake success and never a silent switch to Mock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.ai_engine.v3.music_provider import (
    MusicGenerationProvider,
    MusicProviderFailureV3,
)
from backend.ai_engine.v3.stability_music_provider import (
    DEFAULT_STABILITY_MODEL,
    STABILITY_DEFAULT_BASE_URL,
    StabilityMusicProvider,
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
    api_key = environment.get("STABILITY_API_KEY", "").strip()
    base_url = environment.get("MUSIC_PROVIDER_BASE_URL", "").strip()
    model = environment.get("MUSIC_PROVIDER_MODEL", "").strip() or DEFAULT_STABILITY_MODEL

    if name == "stability":
        if not api_key or model != DEFAULT_STABILITY_MODEL:
            # Fail closed: readiness stays not_configured until the Owner
            # provides a complete, valid Stability configuration.
            return MusicProviderBundle(
                provider=NotConfiguredMusicProvider(provider_name="stability"),
                health=ProviderHealth(
                    status="not_configured",
                    provider_kind="cloud",
                    provider="stability",
                    model=model if api_key else None,
                    checked_at=datetime.now(timezone.utc),
                    capabilities=ProviderCapabilities(
                        structured_json=False,
                        max_input_characters=1,
                    ),
                    safe_message=(
                        "Stability 音乐生成配置不完整（需要 STABILITY_API_KEY 与 "
                        "stable-audio-2.5 模型）。"
                    ),
                ),
            )
        provider = StabilityMusicProvider(
            api_key=api_key,
            model=model,
            base_url=base_url or STABILITY_DEFAULT_BASE_URL,
            media_root=environment.get("HARMONY_MEDIA_ROOT") or None,
        )
        return MusicProviderBundle(
            provider=provider,
            health=provider.health(),
        )
    if name == "minimax":
        # MiniMax is BLOCKED_BY_PROVIDER_ENTITLEMENT for Sprint 5 (Owner real
        # smoke: HTTP 410 / provider code 2153). The adapter stays in the tree
        # as an un-enabled historical implementation and must never be selected.
        return MusicProviderBundle(
            provider=NotConfiguredMusicProvider(provider_name="minimax"),
            health=ProviderHealth(
                status="not_configured",
                provider_kind="cloud",
                provider="minimax",
                model=environment.get("MUSIC_PROVIDER_MODEL", "").strip() or None,
                checked_at=datetime.now(timezone.utc),
                capabilities=ProviderCapabilities(
                    structured_json=False,
                    max_input_characters=1,
                ),
                safe_message=(
                    "MiniMax 已标记 BLOCKED_BY_PROVIDER_ENTITLEMENT（Owner Smoke "
                    "HTTP 410/2153），Sprint 5 不启用；代码保留为历史参考。"
                ),
            ),
        )
    if name and base_url and environment.get("MUSIC_PROVIDER_API_KEY", "").strip() and model:
        # A configured-but-unwired provider name still degrades instead of
        # faking generation success (concrete wiring only exists for stability).
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

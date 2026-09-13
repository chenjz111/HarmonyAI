"""Agent 4 music provider bundle — env-driven, secret-safe.

The concrete provider is selected from deployment environment variables only.
``MUSIC_PROVIDER=tokenhub`` with a complete configuration wires the Tencent
Cloud TokenHub / MiniMax music adapter
(backend/ai_engine/v3/tokenhub_minimax_music_provider.py) using
``TOKENHUB_API_KEY`` / ``TOKENHUB_BASE_URL`` / ``TOKENHUB_MUSIC_MODEL``.

Historical / un-enabled implementations kept for review:
* ``stability_music_provider.py`` — Stability Stable Audio 2.5 (smoke tested
  earlier, now NOT the Sprint 5 official provider);
* ``minimax_music_provider.py`` — direct MiniMax Music API
  (``BLOCKED_BY_PROVIDER_ENTITLEMENT``, HTTP 410/2153).
The direct endpoint ``https://api.minimax.io/v1/music_generation`` is forbidden
for Sprint 5 and is never selected by this builder.

Any missing/unknown configuration keeps the NotConfigured provider so generation
degrades to reviewed local matching or an explicit failure — never fake success
and never a silent switch to Mock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.ai_engine.v3.music_provider import (
    MusicGenerationProvider,
    MusicProviderFailureV3,
)
from backend.ai_engine.v3.tokenhub_minimax_music_provider import (
    DEFAULT_TOKENHUB_MUSIC_MODEL,
    TOKENHUB_DEFAULT_BASE_URL,
    TokenHubMinimaxMusicProvider,
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
    tokenhub_key = environment.get("TOKENHUB_API_KEY", "").strip()
    tokenhub_base = environment.get("TOKENHUB_BASE_URL", "").strip()
    tokenhub_model = (
        environment.get("TOKENHUB_MUSIC_MODEL", "").strip()
        or DEFAULT_TOKENHUB_MUSIC_MODEL
    )
    legacy_model = environment.get("MUSIC_PROVIDER_MODEL", "").strip()

    if name == "tokenhub":
        base_ok = (
            not tokenhub_base
            or tokenhub_base.rstrip("/").lower()
            == TOKENHUB_DEFAULT_BASE_URL.rstrip("/").lower()
        )
        if (
            not tokenhub_key
            or tokenhub_model != DEFAULT_TOKENHUB_MUSIC_MODEL
            or not base_ok
        ):
            # Fail closed: readiness stays not_configured until the Owner
            # provides a complete, valid TokenHub configuration. The model must
            # match exactly and the base URL is restricted to the official host
            # so TOKENHUB_API_KEY can never be sent elsewhere.
            if tokenhub_base and not base_ok:
                message = (
                    "腾讯云 TokenHub 配置错误（TOKENHUB_BASE_URL 必须为官方 "
                    f"{TOKENHUB_DEFAULT_BASE_URL}）。"
                )
            else:
                message = (
                    "腾讯云 TokenHub / MiniMax 音乐生成配置不完整（需要 "
                    f"TOKENHUB_API_KEY 与精确模型 {DEFAULT_TOKENHUB_MUSIC_MODEL}）。"
                )
            return MusicProviderBundle(
                provider=NotConfiguredMusicProvider(provider_name="tokenhub"),
                health=ProviderHealth(
                    status="not_configured",
                    provider_kind="cloud",
                    provider="tokenhub",
                    model=tokenhub_model if tokenhub_key else None,
                    checked_at=datetime.now(timezone.utc),
                    capabilities=ProviderCapabilities(
                        structured_json=False,
                        max_input_characters=1,
                    ),
                    safe_message=message,
                ),
            )
        provider = TokenHubMinimaxMusicProvider(
            api_key=tokenhub_key,
            model=tokenhub_model,
            base_url=TOKENHUB_DEFAULT_BASE_URL,
            media_root=environment.get("HARMONY_MEDIA_ROOT") or None,
        )
        return MusicProviderBundle(
            provider=provider,
            health=provider.health(),
        )
    if name == "stability":
        # Stability was smoke tested earlier but is NOT the Sprint 5 official
        # provider anymore; the adapter stays in the tree as history only.
        return MusicProviderBundle(
            provider=NotConfiguredMusicProvider(provider_name="stability"),
            health=ProviderHealth(
                status="not_configured",
                provider_kind="cloud",
                provider="stability",
                model=legacy_model or None,
                checked_at=datetime.now(timezone.utc),
                capabilities=ProviderCapabilities(
                    structured_json=False,
                    max_input_characters=1,
                ),
                safe_message=(
                    "Stability 已调整为历史/未启用实现（Sprint 5 正式 Provider = "
                    "腾讯云 TokenHub / MiniMax）；代码保留为历史参考。"
                ),
            ),
        )
    if name == "minimax":
        # Direct MiniMax is BLOCKED_BY_PROVIDER_ENTITLEMENT for Sprint 5 (Owner
        # smoke: HTTP 410 / provider code 2153). Its adapter stays as history and
        # the direct endpoint https://api.minimax.io/v1/music_generation must
        # never be called.
        return MusicProviderBundle(
            provider=NotConfiguredMusicProvider(provider_name="minimax"),
            health=ProviderHealth(
                status="not_configured",
                provider_kind="cloud",
                provider="minimax",
                model=legacy_model or None,
                checked_at=datetime.now(timezone.utc),
                capabilities=ProviderCapabilities(
                    structured_json=False,
                    max_input_characters=1,
                ),
                safe_message=(
                    "MiniMax 直连已标记 BLOCKED_BY_PROVIDER_ENTITLEMENT（Owner Smoke "
                    "HTTP 410/2153），Sprint 5 不启用；请使用腾讯云 TokenHub。"
                ),
            ),
        )
    if (
        name
        and environment.get("MUSIC_PROVIDER_BASE_URL", "").strip()
        and environment.get("MUSIC_PROVIDER_API_KEY", "").strip()
        and legacy_model
    ):
        # A configured-but-unwired provider name still degrades instead of
        # faking generation success (concrete wiring only exists for tokenhub).
        return MusicProviderBundle(
            provider=NotConfiguredMusicProvider(provider_name=name),
            health=ProviderHealth(
                status="not_configured",
                provider_kind="cloud",
                provider=name,
                model=legacy_model,
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

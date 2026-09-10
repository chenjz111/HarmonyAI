#!/usr/bin/env python
"""Tencent Cloud TokenHub / MiniMax Music real Smoke — Owner machine.

Provider : Tencent Cloud TokenHub / MiniMax
Endpoint : https://tokenhub.tencentmaas.com/v1/wand/minimax-music/generation
Model    : minimax-music-v3.0
Key      : TOKENHUB_API_KEY (environment only)

Readiness rules:
  * key read only from TOKENHUB_API_KEY; never printed or written anywhere;
  * the generation POST is executed exactly once (automatic retry = 0);
  * provider failure -> explicit stable failure (exit 3); never fake success and
    never switch to Mock;
  * success materializes the audio into HARMONY_MEDIA_ROOT (hex decoded or URL
    downloaded immediately) and prints the owned asset path, the measured
    duration and the provider-reported duration converted from ms to seconds.

Usage (PowerShell):
  # readiness pre-flight — sends NO provider request
  python tools/tokenhub_music_smoke.py --check

  # real generation (one POST; only after the Owner confirms the account state)
  $env:MUSIC_PROVIDER="tokenhub"
  $env:TOKENHUB_BASE_URL="https://tokenhub.tencentmaas.com"
  $env:TOKENHUB_MUSIC_MODEL="minimax-music-v3.0"
  $env:TOKENHUB_API_KEY="<real key>"
  $env:HARMONY_MEDIA_ROOT="media"
  python tools/tokenhub_music_smoke.py

Diagnostics: [SMOKE][DIAG] reports the accurate HTTP status code, response
content type, response byte length and JSON-envelope shape. The API key, the
request body and the provider response body text are never printed.

Exit codes: 0 success / 2 readiness fail / 3 provider failure / 4 script error
"""

from __future__ import annotations

import json
import os
import sys
from hashlib import sha256
from pathlib import Path

import requests

from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.ai_engine.v3.tokenhub_minimax_music_provider import (
    DEFAULT_TOKENHUB_MUSIC_MODEL,
    TOKENHUB_DEFAULT_BASE_URL,
    TOKENHUB_MUSIC_PATH,
    TokenHubMinimaxMusicProvider,
    milliseconds_to_seconds,
)
from backend.app.core.audio_duration import mp3_duration_seconds_from_file
from backend.app.schemas.v3.music import ProviderMusicRequest

SMOKE_TONE_PROFILE = {
    "schema_version": "tone_profile_v3.0",
    "status": "available",
    "weights": {
        "jiao": 0.2,
        "zhi": 0.2,
        "gong": 0.2,
        "shang": 0.2,
        "yu": 0.2,
    },
    "dominant_tone": "gong",
    "score_semantics": "relative_tone_distribution",
    "mapping_version": "v3.0-approved",
    "basis": {"diagnosis_id": "smoke_rx", "supporting_fact_ids": []},
}

SMOKE_GENERATION_SPEC = {
    "schema_version": "generation_spec_v3.0",
    "tone_profile": SMOKE_TONE_PROFILE,
    "bpm": 60,
    "duration_seconds": 60,
    "instruments": ["guqin", "xiao"],
    "ambient_sounds": [],
    "structure": {"intro_seconds": 6, "main_seconds": 48, "outro_seconds": 6},
    "energy_curve": "gentle_decline",
    "forbidden_constraints": [],
    "fallback_policy": {"allow_local_matching": False},
}


class _DiagnosticPoster:
    """JSON poster wrapper recording SAFE diagnostics (no body, no key)."""

    def __init__(self, inner=None) -> None:
        self._inner = inner
        self.status_code: int | None = None
        self.content_type: str | None = None
        self.body_bytes: int | None = None
        self.body_is_json: bool | None = None
        self.transport_error: str | None = None

    def __call__(self, url, *, headers, json_payload, timeout):
        inner = self._inner or requests.post
        try:
            response = inner(
                url, headers=headers, json=json_payload, timeout=timeout
            )
        except BaseException as exc:  # record type only, never the message
            self.transport_error = type(exc).__name__
            raise
        self.status_code = int(getattr(response, "status_code", 0))
        header_map = getattr(response, "headers", {}) or {}
        self.content_type = str(header_map.get("content-type", "")) or None
        content = getattr(response, "content", b"") or b""
        self.body_bytes = len(content)
        self.body_is_json = self._looks_like_json(getattr(response, "text", "") or "")
        return response

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        stripped = text.lstrip()
        if not stripped or stripped[0] not in "{[":
            return False
        try:
            json.loads(stripped)
        except (ValueError, TypeError):
            return False
        return True

    def safe_fields(self) -> dict[str, object]:
        return {
            "http_status": self.status_code,
            "content_type": self.content_type,
            "response_bytes": self.body_bytes,
            "response_is_json": self.body_is_json,
            "transport_error": self.transport_error,
        }


def _print_diagnostics(poster: _DiagnosticPoster) -> None:
    fields = poster.safe_fields()
    rendered = ", ".join(f"{key}={value}" for key, value in fields.items())
    print(f"[SMOKE][DIAG] {rendered}", flush=True)
    if poster.status_code is not None:
        print(
            f"[SMOKE][DIAG] accurate_http_status={poster.status_code}", flush=True
        )


def _fail(message: str, code: int) -> int:
    print(f"[SMOKE][FAIL] {message}", flush=True)
    return code


def _check_mode(
    *, provider_name: str, model: str, base_url: str, media_root: str, has_key: bool
) -> int:
    print("[SMOKE][CHECK] no POST will be sent (readiness pre-flight only)", flush=True)
    print(f"[SMOKE][CHECK] MUSIC_PROVIDER={provider_name or '<unset>'}", flush=True)
    print(f"[SMOKE][CHECK] TOKENHUB_MUSIC_MODEL={model}", flush=True)
    print(f"[SMOKE][CHECK] base_url={base_url}{TOKENHUB_MUSIC_PATH}", flush=True)
    print(f"[SMOKE][CHECK] HARMONY_MEDIA_ROOT={media_root}", flush=True)
    print(f"[SMOKE][CHECK] TOKENHUB_API_KEY_present={bool(has_key)}", flush=True)
    print(
        "[SMOKE][CHECK] planned json body=model,prompt,is_instrumental=true,"
        "output_format=url,audio_setting.format=mp3",
        flush=True,
    )
    print(
        f"[SMOKE][CHECK] planned duration_seconds="
        f"{SMOKE_GENERATION_SPEC['duration_seconds']}, single POST, automatic retry=0",
        flush=True,
    )
    if provider_name != "tokenhub" or not model.startswith("minimax-music") or not has_key:
        return _fail("readiness check failed（配置不完整，未发送任何请求）", 2)
    print("[SMOKE][CHECK] readiness=READY", flush=True)
    return 0


def main() -> int:
    provider_name = os.environ.get("MUSIC_PROVIDER", "").strip().lower()
    model = (
        os.environ.get("TOKENHUB_MUSIC_MODEL", "").strip()
        or DEFAULT_TOKENHUB_MUSIC_MODEL
    )
    api_key = os.environ.get("TOKENHUB_API_KEY", "").strip()
    base_url = (
        os.environ.get("TOKENHUB_BASE_URL", "").strip() or TOKENHUB_DEFAULT_BASE_URL
    )
    media_root = os.environ.get("HARMONY_MEDIA_ROOT", "media").strip() or "media"

    if "--check" in sys.argv:
        return _check_mode(
            provider_name=provider_name,
            model=model,
            base_url=base_url,
            media_root=media_root,
            has_key=bool(api_key),
        )

    if provider_name != "tokenhub":
        return _fail(
            "MUSIC_PROVIDER 必须为 tokenhub（缺配置保持 readiness fail，绝不静默切 Mock）。",
            2,
        )
    if not api_key:
        return _fail("缺少 TOKENHUB_API_KEY（只从环境变量读取）。", 2)
    if not model.startswith("minimax-music"):
        return _fail("TOKENHUB_MUSIC_MODEL 必须为 minimax-music-* 模型。", 2)

    diagnostics = _DiagnosticPoster()
    print(
        f"[SMOKE] tokenhub provider model={model} "
        f"endpoint={base_url}{TOKENHUB_MUSIC_PATH} media_root={media_root}",
        flush=True,
    )
    try:
        provider = TokenHubMinimaxMusicProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            media_root=media_root,
            poster=diagnostics,
        )
    except MusicProviderFailureV3 as exc:
        return _fail(f"Provider 初始化失败：{exc.error_code}", 2)

    request = ProviderMusicRequest(
        provider_request_id="smoke-tokenhub-1",
        generation_spec=SMOKE_GENERATION_SPEC,  # type: ignore[arg-type]
        output_format="mp3",
        callback_ref=None,
    )
    try:
        task = provider.create_task(request)
    except MusicProviderFailureV3 as exc:
        _print_diagnostics(diagnostics)
        return _fail(
            f"TokenHub 真实调用失败：code={exc.error_code} retryable={exc.retryable} "
            f"message={exc.safe_message}",
            3,
        )
    _print_diagnostics(diagnostics)
    if task.status != "succeeded" or not task.asset_locator:
        return _fail("TokenHub 返回非成功结果（不允许伪装成功）。", 3)

    asset_path = Path(task.asset_locator)
    if not asset_path.is_file():
        return _fail(f"音频资产未落盘：{task.asset_locator}", 4)
    digest = sha256(asset_path.read_bytes()).hexdigest()
    size = asset_path.stat().st_size
    measured = mp3_duration_seconds_from_file(asset_path)
    meta = provider.last_run_metadata
    reported_ms = meta.get("provider_reported_duration_ms")
    reported_seconds = (
        milliseconds_to_seconds(reported_ms)
        if isinstance(reported_ms, (int, float))
        else None
    )
    print(
        f"[SMOKE][OK] status=succeeded provider_task_id={task.provider_task_id}\n"
        f"[SMOKE][OK] provider={meta.get('provider')} label={meta.get('provider_label')}\n"
        f"[SMOKE][OK] trace_id={meta.get('trace_id')} request_id={meta.get('request_id')} "
        f"total_tokens={meta.get('total_tokens')}\n"
        f"[SMOKE][OK] owned asset={asset_path}\n"
        f"[SMOKE][OK] size={size} bytes sha256={digest}\n"
        f"[SMOKE][OK] measured_duration_seconds={measured if measured is not None else 'n/a'}\n"
        f"[SMOKE][OK] provider_reported music_duration_ms={reported_ms} "
        f"-> seconds={reported_seconds}\n"
        f"[SMOKE][OK] POST count = {provider.post_calls} (automatic retry = 0), "
        f"download calls = {provider.download_calls}\n"
        f"[SMOKE][OK] Player 通过受控 /api/v3/music/assets/{{id}}/stream 读取，"
        f"不保存 Provider 临时 URL。",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

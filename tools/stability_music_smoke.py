#!/usr/bin/env python
"""Stability AI Stable Audio 2.5 real Smoke — run on the Owner machine.

Owner decision:
  Provider : Stability AI
  Model    : stable-audio-2.5
  Endpoint : https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio
  Status   : OWNER_APPROVED_FOR_SPRINT5_REAL_MODE

Readiness rules:
  * key read only from STABILITY_API_KEY (environment / deployment secret);
  * missing key or wrong model -> explicit readiness failure (exit 2);
  * generation POST is executed exactly once (automatic retry = 0);
  * real failure -> explicit stable failure (exit 3); never fake success and
    never switch to Mock;
  * success materializes the audio/mpeg bytes under HARMONY_MEDIA_ROOT and
    prints the owned asset path + measured duration + sha256.

Usage (PowerShell):
  # readiness pre-flight — sends NO provider request (safe before top-up)
  python tools/stability_music_smoke.py --check

  # real smoke (only after the Owner confirms balance is topped up)
  $env:MUSIC_PROVIDER="stability"
  $env:MUSIC_PROVIDER_MODEL="stable-audio-2.5"
  $env:MUSIC_PROVIDER_BASE_URL="https://api.stability.ai"   # optional
  $env:STABILITY_API_KEY="<real key>"
  $env:HARMONY_MEDIA_ROOT="media"
  python tools/stability_music_smoke.py

Diagnostics: the script records the ACCURATE HTTP status code, response
content type, response byte length and JSON-envelope shape via
``[SMOKE][DIAG]`` lines. It never prints the API key, the request body or the
provider response body text.

Exit codes:
  0  real generation succeeded and the asset is locally playable
  2  configuration missing/invalid (readiness fail)
  3  Stability provider rejected/failed the request
  4  smoke script error
"""

from __future__ import annotations

import os
import sys
from hashlib import sha256
from pathlib import Path

import requests

from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.ai_engine.v3.stability_music_provider import (
    DEFAULT_STABILITY_MODEL,
    STABILITY_DEFAULT_BASE_URL,
    StabilityMusicProvider,
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
    """Wraps the HTTP poster and records SAFE provider diagnostics only.

    Captures the exact HTTP status code (the adapter intentionally hides raw
    statuses from public failures), the response content type, the response
    byte length and whether the body looked like a JSON envelope. It never
    stores or prints the API key, the request body or the response body text.
    """

    def __init__(self, inner=None) -> None:
        self._inner = inner
        self.status_code: int | None = None
        self.content_type: str | None = None
        self.body_bytes: int | None = None
        self.body_is_json: bool | None = None
        self.transport_error: str | None = None
        self.post_count = 0

    def __call__(self, url, *, headers, data, files, timeout):
        inner = self._inner or requests.post
        self.post_count += 1
        try:
            response = inner(
                url, headers=headers, data=data, files=files, timeout=timeout
            )
        except Exception as exc:  # record type only, never the message
            self.transport_error = type(exc).__name__
            raise
        self.status_code = int(getattr(response, "status_code", 0))
        header_map = getattr(response, "headers", {}) or {}
        self.content_type = str(header_map.get("content-type", "")) or None
        content = getattr(response, "content", b"") or b""
        self.body_bytes = len(content)
        self.body_is_json = self._is_json_content_type(self.content_type)
        return response

    @staticmethod
    def _is_json_content_type(content_type: str | None) -> bool:
        media_type = (content_type or "").partition(";")[0].strip().lower()
        return media_type == "application/json" or media_type.endswith("+json")

    def safe_fields(self) -> dict[str, object]:
        """JSON-serializable, secret-free diagnostics for the smoke log."""
        return {
            "http_status": self.status_code,
            "content_type": self.content_type,
            "response_bytes": self.body_bytes,
            "response_is_json": self.body_is_json,
            "transport_error": self.transport_error,
            "post_count": self.post_count,
        }


def _print_diagnostics(poster: _DiagnosticPoster) -> None:
    fields = poster.safe_fields()
    rendered = ", ".join(f"{key}={value}" for key, value in fields.items())
    print(f"[SMOKE][DIAG] {rendered}", flush=True)
    if poster.status_code is not None:
        print(
            f"[SMOKE][DIAG] accurate_http_status={poster.status_code} "
            f"(raw provider status is intentionally not hidden anymore)",
            flush=True,
        )


def _fail(message: str, code: int) -> int:
    print(f"[SMOKE][FAIL] {message}", flush=True)
    return code


def _check_mode(
    *,
    provider_name: str,
    model: str,
    base_url: str,
    media_root: str,
    has_key: bool,
) -> int:
    """Readiness-only pre-flight; sends NO provider request."""
    print("[SMOKE][CHECK] no POST will be sent (readiness pre-flight only)", flush=True)
    print(f"[SMOKE][CHECK] MUSIC_PROVIDER={provider_name or '<unset>'}", flush=True)
    print(f"[SMOKE][CHECK] MUSIC_PROVIDER_MODEL={model}", flush=True)
    print(f"[SMOKE][CHECK] base_url={base_url}", flush=True)
    print(f"[SMOKE][CHECK] HARMONY_MEDIA_ROOT={media_root}", flush=True)
    print(f"[SMOKE][CHECK] STABILITY_API_KEY_present={bool(has_key)}", flush=True)
    print(
        "[SMOKE][CHECK] planned multipart fields="
        "model,prompt,duration,steps,cfg_scale (seed omitted)",
        flush=True,
    )
    print(
        f"[SMOKE][CHECK] planned duration_seconds="
        f"{SMOKE_GENERATION_SPEC['duration_seconds']}, single POST, automatic retry=0",
        flush=True,
    )
    if provider_name != "stability" or model != DEFAULT_STABILITY_MODEL or not has_key:
        return _fail("readiness check failed（配置不完整，未发送任何请求）", 2)
    print("[SMOKE][CHECK] readiness=READY", flush=True)
    return 0


def main() -> int:
    provider_name = os.environ.get("MUSIC_PROVIDER", "").strip().lower()
    model = os.environ.get("MUSIC_PROVIDER_MODEL", "").strip() or DEFAULT_STABILITY_MODEL
    api_key = os.environ.get("STABILITY_API_KEY", "").strip()
    base_url = os.environ.get("MUSIC_PROVIDER_BASE_URL", "").strip() or STABILITY_DEFAULT_BASE_URL
    media_root = os.environ.get("HARMONY_MEDIA_ROOT", "media").strip() or "media"

    if "--check" in sys.argv:
        return _check_mode(
            provider_name=provider_name,
            model=model,
            base_url=base_url,
            media_root=media_root,
            has_key=bool(api_key),
        )

    if provider_name != "stability":
        return _fail(
            "MUSIC_PROVIDER 必须为 stability（缺配置保持 readiness fail，绝不静默切 Mock）。",
            2,
        )
    if not api_key:
        return _fail("缺少 STABILITY_API_KEY（只从环境变量读取）。", 2)
    if model != DEFAULT_STABILITY_MODEL:
        return _fail(f"MUSIC_PROVIDER_MODEL 必须为 {DEFAULT_STABILITY_MODEL}。", 2)

    diagnostics = _DiagnosticPoster()
    print(
        f"[SMOKE] stability provider model={model} base_url={base_url} "
        f"media_root={media_root}",
        flush=True,
    )
    try:
        provider = StabilityMusicProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            media_root=media_root,
            poster=diagnostics,
        )
    except MusicProviderFailureV3 as exc:
        return _fail(f"Provider 初始化失败：{exc.error_code}", 2)

    request = ProviderMusicRequest(
        provider_request_id="smoke-stability-1",
        generation_spec=SMOKE_GENERATION_SPEC,  # type: ignore[arg-type]
        output_format="mp3",
        callback_ref=None,
    )
    try:
        task = provider.create_task(request)
    except MusicProviderFailureV3 as exc:
        _print_diagnostics(diagnostics)
        return _fail(
            f"Stability 真实调用失败：code={exc.error_code} retryable={exc.retryable} "
            f"message={exc.safe_message}",
            3,
        )
    _print_diagnostics(diagnostics)
    if task.status != "succeeded" or not task.asset_locator:
        return _fail("Stability 返回非成功结果（不允许伪装成功）。", 3)

    asset_path = Path(task.asset_locator)
    if not asset_path.is_file():
        return _fail(f"音频资产未落盘：{task.asset_locator}", 4)
    digest = sha256(asset_path.read_bytes()).hexdigest()
    size = asset_path.stat().st_size
    measured = mp3_duration_seconds_from_file(asset_path)
    print(
        f"[SMOKE][OK] status=succeeded provider_task_id={task.provider_task_id}\n"
        f"[SMOKE][OK] owned asset={asset_path}\n"
        f"[SMOKE][OK] size={size} bytes sha256={digest}\n"
        f"[SMOKE][OK] measured_duration_seconds={measured if measured is not None else 'n/a'}\n"
        f"[SMOKE][OK] POST count = {provider.post_calls} (automatic retry = 0)\n"
        f"[SMOKE][OK] Player 通过受控 /api/v3/music/assets/{{id}}/stream 读取，"
        f"不使用临时 Provider URL。",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

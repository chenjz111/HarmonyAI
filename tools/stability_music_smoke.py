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
  $env:MUSIC_PROVIDER="stability"
  $env:MUSIC_PROVIDER_MODEL="stable-audio-2.5"
  $env:MUSIC_PROVIDER_BASE_URL="https://api.stability.ai"   # optional
  $env:STABILITY_API_KEY="<real key>"
  $env:HARMONY_MEDIA_ROOT="media"
  python tools/stability_music_smoke.py

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


def _fail(message: str, code: int) -> int:
    print(f"[SMOKE][FAIL] {message}", flush=True)
    return code


def main() -> int:
    provider_name = os.environ.get("MUSIC_PROVIDER", "").strip().lower()
    model = os.environ.get("MUSIC_PROVIDER_MODEL", "").strip() or DEFAULT_STABILITY_MODEL
    api_key = os.environ.get("STABILITY_API_KEY", "").strip()
    base_url = os.environ.get("MUSIC_PROVIDER_BASE_URL", "").strip() or STABILITY_DEFAULT_BASE_URL
    media_root = os.environ.get("HARMONY_MEDIA_ROOT", "media").strip() or "media"

    if provider_name != "stability":
        return _fail(
            "MUSIC_PROVIDER 必须为 stability（缺配置保持 readiness fail，绝不静默切 Mock）。",
            2,
        )
    if not api_key:
        return _fail("缺少 STABILITY_API_KEY（只从环境变量读取）。", 2)
    if model != DEFAULT_STABILITY_MODEL:
        return _fail(f"MUSIC_PROVIDER_MODEL 必须为 {DEFAULT_STABILITY_MODEL}。", 2)

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
        return _fail(
            f"Stability 真实调用失败：code={exc.error_code} retryable={exc.retryable} "
            f"message={exc.safe_message}",
            3,
        )
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

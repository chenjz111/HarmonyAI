#!/usr/bin/env python
"""MiniMax Music smoke — HISTORY / UN-ENABLED reference (do not run as Sprint 5).

Owner real smoke returned HTTP 410 / provider code 2153 for the MiniMax account
(BLOCKED_BY_PROVIDER_ENTITLEMENT). Sprint 5 real Provider is Stability AI
Stable Audio 2.5 — use tools/stability_music_smoke.py instead. This file stays
only as a historical record for the retained MiniMax adapter implementation.

Readiness rules (docs/sprint5/provider-decision-record-music.md):
  * configuration comes only from environment variables;
  * missing/invalid MiniMax config -> explicit readiness failure (exit 2);
  * provider failure -> explicit stable failure (exit 3); never fake success;
  * success materializes the audio into HARMONY_MEDIA_ROOT and prints the
    owned asset path + sha256 (never the vendor URL or key).
"""

from __future__ import annotations

import os
import sys
from hashlib import sha256
from pathlib import Path

from backend.ai_engine.v3.minimax_music_provider import (
    DEFAULT_MINIMAX_BASE_URL,
    MINIMAX_MODELS,
    MiniMaxMusicProvider,
)
from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
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
    "structure": {"intro_seconds": 10, "main_seconds": 40, "outro_seconds": 10},
    "energy_curve": "gentle_decline",
    "forbidden_constraints": [],
    "fallback_policy": {"allow_local_matching": False},
}


def _fail(message: str, code: int) -> int:
    print(f"[SMOKE][FAIL] {message}", flush=True)
    return code


def main() -> int:
    api_key = os.environ.get("MUSIC_PROVIDER_API_KEY", "").strip()
    model = os.environ.get("MUSIC_PROVIDER_MODEL", "").strip()
    base_url = os.environ.get("MUSIC_PROVIDER_BASE_URL", "").strip() or DEFAULT_MINIMAX_BASE_URL
    provider_name = os.environ.get("MUSIC_PROVIDER", "").strip().lower()
    media_root = os.environ.get("HARMONY_MEDIA_ROOT", "media").strip() or "media"

    if provider_name != "minimax":
        return _fail(
            "MUSIC_PROVIDER 必须为 minimax（当前缺配置时保持 readiness fail，绝不静默切 Mock）。",
            2,
        )
    if not api_key:
        return _fail("缺少 MUSIC_PROVIDER_API_KEY（只从环境变量读取）。", 2)
    if not model:
        return _fail("缺少 MUSIC_PROVIDER_MODEL（示例 music-3.0）。", 2)
    if model not in MINIMAX_MODELS:
        return _fail(f"MUSIC_PROVIDER_MODEL={model!r} 不在官方模型清单内。", 2)

    print(
        f"[SMOKE] minimax provider={provider_name} model={model} "
        f"base_url={base_url} media_root={media_root}",
        flush=True,
    )
    try:
        provider = MiniMaxMusicProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            media_root=media_root,
        )
    except MusicProviderFailureV3 as exc:
        return _fail(f"Provider 初始化失败：{exc.error_code}", 2)

    request = ProviderMusicRequest(
        provider_request_id="smoke-minimax-1",
        generation_spec=SMOKE_GENERATION_SPEC,  # type: ignore[arg-type]
        output_format="mp3",
        callback_ref=None,
    )
    try:
        task = provider.create_task(request)
    except MusicProviderFailureV3 as exc:
        return _fail(
            f"MiniMax 真实调用失败：code={exc.error_code} retryable={exc.retryable} "
            f"message={exc.safe_message}",
            3,
        )
    if task.status != "succeeded" or not task.asset_locator:
        return _fail("MiniMax 返回非成功结果（不允许伪装成功）。", 3)

    asset_path = Path(task.asset_locator)
    if not asset_path.is_file():
        return _fail(f"音频资产未落盘：{task.asset_locator}", 4)
    digest = sha256(asset_path.read_bytes()).hexdigest()
    size = asset_path.stat().st_size
    print(
        f"[SMOKE][OK] status=succeeded provider_task_id={task.provider_task_id}\n"
        f"[SMOKE][OK] owned asset={asset_path}\n"
        f"[SMOKE][OK] size={size} bytes sha256={digest}\n"
        f"[SMOKE][OK] Player 通过受控 /api/v3/music/assets/{{id}}/stream 读取，"
        f"不使用临时 Provider URL。",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

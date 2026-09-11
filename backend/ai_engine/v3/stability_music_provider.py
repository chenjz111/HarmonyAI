"""Agent 4 — Stability AI Stable Audio 2.5 adapter (real provider, fail-closed).

Owner decision (docs/sprint5/agent4-stability-smoke.md):

  Provider : Stability AI
  Model    : stable-audio-2.5
  Endpoint : https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio
  Status   : OWNER_APPROVED_FOR_SPRINT5_REAL_MODE

Design boundaries
-----------------
* Credentials come only from the deployment environment variable
  ``STABILITY_API_KEY`` via ``build_music_provider_bundle``; they are never
  written into code, tests, logs, health payloads or client-visible tasks.
* The request uses official ``multipart/form-data`` produced by the ``requests``
  client (no hand-written Content-Type or boundary). The generation POST is
  executed exactly once — automatic retry is hard-coded to 0 so a transient
  failure can never cause a duplicate paid generation.
* The real ``audio/mpeg`` binary response is validated (content type + mp3
  magic) and materialized into the project-owned media root before the task can
  be reported as succeeded. The vendor never provides a stable locator here, so
  there is no temporary-URL leakage by construction.
* Failure modes (missing key/permission/balance/timeout/5xx/empty audio) always
  surface as explicit stable failures; Real mode never switches to Mock and
  never fabricates success.
* Capability flags are honest: Stable Audio 2.5 text-to-audio is a synchronous
  request/response API (no progress/cancel surface), documented duration range
  1-190 s.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import time
from typing import Protocol

import requests

from backend.ai_engine.v3.music_provider import (
    MusicProviderFailureV3,
    validate_provider_request_capabilities,
)
from backend.app.schemas.v3.common import (
    ProviderCapabilities,
    ProviderHealth,
)
from backend.app.schemas.v3.music import (
    MusicProviderCapabilities,
    ProviderMusicRequest,
    ProviderTask,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

STABILITY_DEFAULT_BASE_URL = "https://api.stability.ai"
STABILITY_AUDIO_PATH = "/v2beta/audio/stable-audio-2/text-to-audio"
DEFAULT_STABILITY_MODEL = "stable-audio-2.5"

# Stable Audio 2.5 documented duration envelope (1-190 s per model card and the
# official partner integration). The Owner real smoke used 60 s successfully.
STABILITY_MAX_DURATION_SECONDS = 190

# Prompt length safety cap (documented model input length limit).
STABILITY_PROMPT_MAX_LENGTH = 10000

# Reference Chinese-instrument vocabulary rendered by the app through the
# natural-language prompt (five-tone mapping). This is NOT a hard API whitelist
# and per-instrument fidelity must be confirmed by real smoke.
REFERENCE_INSTRUMENTS = (
    "guqin",
    "xiao",
    "guzheng",
    "pipa",
    "erhu",
    "dizi",
    "sheng",
    "xun",
    "bianzhong",
)

_TONE_MOOD = {
    "gong": "steady, grounded, calm earth energy",
    "shang": "clear, bright metal energy",
    "jiao": "gentle, flowing wood energy",
    "zhi": "warm, radiant fire energy",
    "yu": "fluid, deep water energy",
}

_MEDIA_ROOT_ENV = "HARMONY_MEDIA_ROOT"
_GENERATED_SUBDIR = Path("generated") / "stability"

_PUBLIC_ERRORS = {
    "GENERATION_PROVIDER_UNAVAILABLE": (
        "GENERATION_PROVIDER_UNAVAILABLE",
        "音乐生成服务暂时不可用。",
        True,
    ),
    "GENERATION_PROVIDER_TIMEOUT": (
        "GENERATION_PROVIDER_TIMEOUT",
        "音乐生成服务响应超时，请稍后重试。",
        True,
    ),
    "GENERATION_PROVIDER_RATE_LIMITED": (
        "GENERATION_PROVIDER_RATE_LIMITED",
        "音乐生成服务繁忙，请稍后重试。",
        True,
    ),
    "GENERATION_PROVIDER_AUTH_FAILED": (
        "GENERATION_PROVIDER_AUTH_FAILED",
        "音乐生成服务认证失败，请联系管理员。",
        False,
    ),
    "GENERATION_PROVIDER_REJECTED": (
        "GENERATION_PROVIDER_REJECTED",
        "音乐生成服务拒绝了本次请求（参数、额度或内容受限）。",
        False,
    ),
}


class StabilityHttpResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    text: str


class StabilityPoster(Protocol):
    def __call__(
        self,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, object],
        files: dict[str, tuple[str, bytes]] | None,
        timeout: tuple[float, float],
    ) -> StabilityHttpResponse: ...


def _requests_poster(
    url: str,
    *,
    headers: dict[str, str],
    data: dict[str, object],
    files: dict[str, tuple[str, bytes]] | None,
    timeout: tuple[float, float],
) -> StabilityHttpResponse:
    return requests.post(
        url,
        headers=headers,
        data=data,
        files=files,
        timeout=timeout,
    )  # type: ignore[return-value]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_prompt(request: ProviderMusicRequest) -> str:
    """Deterministic, medical-neutral prompt from the structured spec."""
    spec = request.generation_spec
    tone_profile = spec.tone_profile
    tone = getattr(tone_profile, "dominant_tone", None) if tone_profile else None
    instruments = ", ".join(spec.instruments) or "warm acoustic textures"
    ambient_parts = [f"soft {item} ambience" for item in spec.ambient_sounds]
    structure = spec.structure
    parts = ["Traditional Chinese instrumental healing music"]
    if tone:
        mood = _TONE_MOOD.get(tone, "steady, calm")
        parts.append(f"in {tone} mode ({mood})")
    parts.extend(
        [
            f"bpm {spec.bpm}",
            f"total duration {spec.duration_seconds} seconds",
            f"Instruments: {instruments}",
            (
                f"Structure: intro {structure.intro_seconds}s, "
                f"main {structure.main_seconds}s, outro {structure.outro_seconds}s"
            ),
            f"Energy: {spec.energy_curve}",
        ]
    )
    if ambient_parts:
        parts.append("Atmosphere: " + ", ".join(ambient_parts) + ".")
    if spec.forbidden_constraints:
        parts.append("Avoid: " + ", ".join(spec.forbidden_constraints) + ".")
    prompt = " ".join(parts) + "."
    if len(prompt) > STABILITY_PROMPT_MAX_LENGTH:
        raise MusicProviderFailureV3(
            "GENERATION_PROVIDER_REJECTED",
            retryable=False,
            safe_message="音乐生成提示词过长，无法提交生成服务。",
        )
    return prompt


def _looks_like_mp3(payload: bytes) -> bool:
    if not payload:
        return False
    if payload.startswith(b"ID3"):
        return True
    if len(payload) >= 2 and payload[0] == 0xFF and (payload[1] & 0xE0) == 0xE0:
        return True
    return False


class StabilityMusicProvider:
    """Stable Audio 2.5 text-to-audio adapter behind the frozen protocol."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_STABILITY_MODEL,
        base_url: str = STABILITY_DEFAULT_BASE_URL,
        media_root: str | os.PathLike[str] | None = None,
        connect_timeout: float = 30.0,
        read_timeout: float = 300.0,
        poster: StabilityPoster | None = None,
        provider_name: str = "stability",
    ) -> None:
        if not api_key or not api_key.strip():
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="音乐生成服务尚未配置。",
            )
        if not model or model.strip() != DEFAULT_STABILITY_MODEL:
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="Stability 音乐模型配置无效（Sprint 5 仅支持 stable-audio-2.5）。",
            )
        self._api_key = api_key
        self.model = model
        self.provider_name = provider_name
        self.base_url = (base_url or STABILITY_DEFAULT_BASE_URL).rstrip("/")
        self.connect_timeout = max(1.0, float(connect_timeout))
        self.read_timeout = max(10.0, float(read_timeout))
        if media_root is not None:
            self.media_root = Path(media_root)
        else:
            self.media_root = Path(os.environ.get(_MEDIA_ROOT_ENV, "media"))
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.poster = poster or _requests_poster
        self._health_status: str = "configured"
        self.last_run_metadata: dict[str, object] = {}
        self.post_calls = 0

    # ------------------------------------------------------------------ #
    # Provider protocol
    # ------------------------------------------------------------------ #

    def capabilities(self) -> MusicProviderCapabilities:
        return MusicProviderCapabilities(
            max_duration_seconds=STABILITY_MAX_DURATION_SECONDS,
            supports_progress=False,
            supports_cancel=False,
            supported_instruments=list(REFERENCE_INSTRUMENTS),
            supported_formats=["mp3"],
        )

    def health(self) -> ProviderHealth:
        safe_message = None
        if self._health_status == "degraded":
            safe_message = "音乐生成服务暂时不稳定。"
        elif self._health_status == "down":
            safe_message = "音乐生成服务暂时不可用。"
        return ProviderHealth(
            status=self._health_status,  # type: ignore[arg-type]
            provider_kind="cloud",
            provider=self.provider_name,
            model=self.model,
            checked_at=_utc_now(),
            capabilities=ProviderCapabilities(
                structured_json=False,
                max_input_characters=STABILITY_PROMPT_MAX_LENGTH,
            ),
            safe_message=safe_message,
        )

    def create_task(self, request: ProviderMusicRequest) -> ProviderTask:
        validate_provider_request_capabilities(request, self.capabilities())
        started = time.perf_counter()
        prompt = _build_prompt(request)
        duration_seconds = int(request.generation_spec.duration_seconds)
        # Multipart field names follow the Owner-verified successful request and
        # the official Stable Audio 2.5 text-to-audio schema:
        #   model / prompt / duration / steps / cfg_scale / seed
        # (seed is omitted so every generation is non-deterministic; billing is
        # idempotency-protected by the service layer).
        data: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "duration": duration_seconds,
            "steps": 8,
            "cfg_scale": 1.0,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "audio/*",
        }
        # requests generates the multipart boundary; the empty named part keeps
        # the body multipart/form-data exactly like the official sample flow.
        files = {"none": ("", b"")}
        url = f"{self.base_url}{STABILITY_AUDIO_PATH}"

        # REAL RULE: exactly one POST, automatic retry is 0 — a retry would risk
        # a duplicate paid generation. Service-level idempotency is the only
        # allowed protection.
        self.post_calls += 1
        try:
            response = self.poster(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=(self.connect_timeout, self.read_timeout),
            )
        except BaseException as exc:
            error = self._classify_transport_error(exc)
            self._record_failure(error, started, 1)
            raise error from exc

        task = self._parse_response(response=response, request=request, started=started)
        if task.status == "succeeded":
            self._health_status = "healthy"
        return task

    def get_task(self, provider_task_id: str) -> ProviderTask:
        # Stable Audio 2.5 text-to-audio is a synchronous request/response API;
        # there is no documented task query surface. Refuse to invent one.
        raise MusicProviderFailureV3(
            "GENERATION_PROVIDER_UNAVAILABLE",
            retryable=True,
            safe_message="当前音乐生成服务不支持任务轮询。",
        )

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        raise MusicProviderFailureV3(
            "GENERATION_CANCEL_UNSUPPORTED",
            retryable=False,
            safe_message="当前生成服务不支持取消任务。",
        )

    # ---------------------------------------------------------------- #
    # Async protocol
    # ---------------------------------------------------------------- #

    async def acreate_task(self, request: ProviderMusicRequest) -> ProviderTask:
        return await asyncio.to_thread(self.create_task, request)

    async def aget_task(self, provider_task_id: str) -> ProviderTask:
        return self.get_task(provider_task_id)

    async def acancel_task(self, provider_task_id: str) -> ProviderTask:
        return self.cancel_task(provider_task_id)

    # ------------------------------------------------------------------ #
    # Response handling
    # ------------------------------------------------------------------ #

    def _parse_response(
        self,
        *,
        response: StabilityHttpResponse,
        request: ProviderMusicRequest,
        started: float,
    ) -> ProviderTask:
        status_code = int(getattr(response, "status_code", 0))
        if status_code != 200:
            error = self._public_failure(self._map_http_status(status_code))
            self._record_failure(error, started, 1)
            raise error from None

        content_type = str(getattr(response, "headers", {}).get("content-type", ""))
        if not content_type.lower().startswith("audio/"):
            # Vendor JSON error envelopes may echo the API key; they are never
            # propagated into stable failures or logs.
            error = self._public_failure("GENERATION_PROVIDER_REJECTED")
            self._record_failure(error, started, 1)
            raise error from None

        audio = getattr(response, "content", None)
        if not isinstance(audio, bytes) or not _looks_like_mp3(audio):
            error = self._public_failure("GENERATION_PROVIDER_REJECTED")
            self._record_failure(error, started, 1)
            raise error from None

        locator = self._materialize_audio(audio)
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        self.last_run_metadata = {
            "provider": self.provider_name,
            "model": self.model,
            "attempts": 1,
            "latency_ms": latency_ms,
            "error_code": None,
        }
        task_id = _safe_task_id(sha256(audio).hexdigest())
        return ProviderTask(
            provider_task_id=task_id,
            status="succeeded",
            progress_value=100,
            asset_locator=locator,
            error_code=None,
        )

    def _materialize_audio(self, payload: bytes) -> str:
        """Store owned binary audio under the project media root."""
        file_name = f"{sha256(payload).hexdigest()[:16]}.mp3"
        target_dir = self.media_root / _GENERATED_SUBDIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file_name
        target.write_bytes(payload)
        return str(target.resolve())

    # ------------------------------------------------------------------ #
    # Error classification
    # ------------------------------------------------------------------ #

    def _map_http_status(self, status_code: int) -> str:
        if status_code in {401, 403}:
            return "GENERATION_PROVIDER_AUTH_FAILED"
        if status_code == 429:
            return "GENERATION_PROVIDER_RATE_LIMITED"
        if 500 <= status_code <= 599:
            return "GENERATION_PROVIDER_UNAVAILABLE"
        # 400/402/404/422/409 -> request/permission/balance/parameter rejected
        return "GENERATION_PROVIDER_REJECTED"

    def _public_failure(self, error_code: str) -> MusicProviderFailureV3:
        normalized, message, retryable = _PUBLIC_ERRORS.get(
            error_code, _PUBLIC_ERRORS["GENERATION_PROVIDER_UNAVAILABLE"]
        )
        return MusicProviderFailureV3(
            normalized,
            retryable=retryable,
            safe_message=message,
        )

    def _classify_transport_error(
        self, exc: BaseException
    ) -> MusicProviderFailureV3:
        if isinstance(exc, (requests.Timeout, TimeoutError)):
            return self._public_failure("GENERATION_PROVIDER_TIMEOUT")
        if isinstance(exc, (requests.RequestException, OSError)):
            return self._public_failure("GENERATION_PROVIDER_UNAVAILABLE")
        return self._public_failure("GENERATION_PROVIDER_UNAVAILABLE")

    def _record_failure(
        self, error: MusicProviderFailureV3, started: float, attempt: int
    ) -> None:
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        self.last_run_metadata = {
            "provider": self.provider_name,
            "model": self.model,
            "attempts": attempt,
            "latency_ms": latency_ms,
            "error_code": error.error_code,
        }
        self._health_status = "degraded" if error.retryable else "down"


def _safe_task_id(hex_digest: str) -> str:
    """Opaque, path-safe provider task id derived from the owned asset hash."""
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "", hex_digest)
    return f"stability-{sanitized[:32]}"

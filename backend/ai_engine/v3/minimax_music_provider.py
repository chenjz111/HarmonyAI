"""Agent 4 — MiniMax Music API adapter (real provider, fail-closed).

Target chain (docs/sprint5/provider-decision-record-music.md):

    GenerationSpec -> MiniMax Music API -> real provider response
    -> owned Audio Asset (media root) -> Player-readable asset

Design boundaries
-----------------
* This adapter is the concrete wiring for ``MUSIC_PROVIDER=minimax``. It never
  fakes generation success and never switches to a Mock provider.
* Credentials are accepted only through constructor arguments produced from
  deployment environment variables by ``build_music_provider_bundle``; they are
  never logged, serialized into health payloads, or returned to clients.
* Capability flags reflect the official MiniMax Music API surface documented at
  https://platform.minimax.io/docs/api-reference/music-generation (Music 3.0 /
  2.6, POST /v1/music_generation). As of this writing the documented API is a
  synchronous request/response interface: there is **no documented music task
  query or cancel endpoint**, so the adapter honestly reports
  ``supports_progress=False`` and ``supports_cancel=False`` and never pretends
  to poll or cancel a MiniMax task.
* The MiniMax result audio is hex or URL addressed and any URL expires after 24
  hours. The adapter therefore materializes the audio into the project-owned
  media root on success and returns that owned local locator, never the vendor
  temporary locator.
* Behavior corners that still require an Owner real-key smoke are marked with
  ``REAL_SMOKE_REQUIRED`` in this module and in the pull-request notes: exact
  model snapshot/version/endpoint/region, real duration envelope, whether the
  create response can carry an in-progress (status=1) payload without a poll
  handle, and per-instrument rendering fidelity.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.ai_engine.providers import (
    ConnectionTimeoutError,
    ReadTimeoutError,
)
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

DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io"
MINIMAX_MUSIC_PATH = "/v1/music_generation"

# Documented MiniMax Music models (music-3.0 recommended; free tiers retired on
# 2026-08-20 for new users). The final pinned snapshot is an Owner smoke record.
MINIMAX_MODELS = frozenset(
    {
        "music-3.0",
        "music-2.6",
        "music-cover",
        "music-3.0-free",
        "music-2.6-free",
        "music-cover-free",
    }
)

# Reference Chinese-instrument vocabulary rendered by the app (five-tone
# mapping). MiniMax consumes these through the natural-language prompt; this is
# NOT a hard API whitelist and each instrument must be confirmed by real smoke.
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

# Conservative duration envelope derived from the Sprint 5 provider comparison
# (10-300 s class) and the frozen GenerationSpec durations used by the app.
# REAL_SMOKE_REQUIRED: record the exact MiniMax output envelope and adjust.
MAX_DURATION_SECONDS = 300

# Prompt length cap documented by MiniMax (1-2000 characters).
MINIMAX_PROMPT_MAX_LENGTH = 2000

_TONE_MOOD = {
    "gong": "steady, grounded, calm earth energy",
    "shang": "clear, bright metal energy",
    "jiao": "gentle, flowing wood energy",
    "zhi": "warm, radiant fire energy",
    "yu": "fluid, deep water energy",
}

# Stable public vocabulary used by the service layer (music_provider.py).
_ERROR_MAPPING = {
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
        "音乐生成服务拒绝了本次请求。",
        False,
    ),
}

# MiniMax base_resp.status_code -> stable public error code.
_MINIMAX_STATUS_CODE_MAP = {
    0: None,
    1002: "GENERATION_PROVIDER_RATE_LIMITED",
    1004: "GENERATION_PROVIDER_AUTH_FAILED",
    1008: "GENERATION_PROVIDER_REJECTED",  # insufficient balance
    1026: "GENERATION_PROVIDER_REJECTED",  # content flagged
    2013: "GENERATION_PROVIDER_REJECTED",  # invalid parameters
    2049: "GENERATION_PROVIDER_AUTH_FAILED",
}

_MEDIA_ROOT_ENV = "HARMONY_MEDIA_ROOT"
_GENERATED_SUBDIR = Path("generated") / "minimax"


class MiniMaxTransport(Protocol):
    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout: float,
    ) -> bytes: ...


class MiniMaxHttpTransport:
    """Default urllib POST transport; raises the provider timeout classes."""

    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        body: bytes,
        timeout: float,
    ) -> bytes:
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError:
            raise
        except TimeoutError as exc:
            raise ReadTimeoutError from exc
        except OSError as exc:
            raise ConnectionTimeoutError from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_provider_task_id(raw: str | None, fallback: str) -> str:
    """Keep vendor ids opaque but path-safe; never expose them to clients."""
    if raw:
        sanitized = re.sub(r"[^A-Za-z0-9_-]", "", raw)
        if sanitized:
            return sanitized[:64]
    return fallback


def _build_prompt(request: ProviderMusicRequest) -> str:
    """Deterministic, medical-neutral prompt from the structured spec.

    The spec carries only tone/parameter fields (no patient text), so the
    prompt cannot leak protected content. When the ToneProfile is insufficient
    no tone claim is made.
    """
    spec = request.generation_spec
    tone_profile = spec.tone_profile
    tone = getattr(tone_profile, "dominant_tone", None) if tone_profile else None
    instruments = ", ".join(spec.instruments) or "warm acoustic textures"
    ambient_parts = [f"soft {item} ambience" for item in spec.ambient_sounds]
    structure = spec.structure
    parts = [
        "Traditional Chinese instrumental healing music",
    ]
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
        parts.append(
            "Avoid: " + ", ".join(spec.forbidden_constraints) + "."
        )
    prompt = " ".join(parts) + "."
    if len(prompt) > MINIMAX_PROMPT_MAX_LENGTH:
        raise MusicProviderFailureV3(
            "GENERATION_PROVIDER_REJECTED",
            retryable=False,
            safe_message="音乐生成提示词过长，无法提交生成服务。",
        )
    return prompt


def _looks_like_audio(payload: bytes) -> bool:
    """Very light format sniff so empty/garbage audio fails explicitly.

    mp3: ID3 tag or 0xFF Ex sync frame; wav: RIFF....WAVE. This is not a full
    decoder; exact container validation stays an Owner smoke item.
    """
    if not payload:
        return False
    if payload.startswith(b"ID3"):
        return True
    if payload[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return True
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WAVE":
        return True
    return False


class MiniMaxMusicProvider:
    """MiniMax Music API adapter implementing the frozen provider protocol.

    ``api_key``/``base_url``/``model`` are passed in by the env-driven builder;
    this class never reads secrets itself, never logs them and never includes
    them in health or task payloads.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        media_root: str | os.PathLike[str] | None = None,
        connect_timeout: float = 15.0,
        read_timeout: float = 240.0,
        max_retries: int = 1,
        transport: MiniMaxTransport | None = None,
        provider_name: str = "minimax",
    ) -> None:
        if not api_key or not api_key.strip():
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="音乐生成服务尚未配置。",
            )
        if not model or not model.strip():
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="音乐生成服务尚未配置。",
            )
        if model not in MINIMAX_MODELS:
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="MiniMax 音乐模型配置无效，请由 Owner 在真实 Smoke 后确认模型快照。",
            )
        self.base_url = (base_url or DEFAULT_MINIMAX_BASE_URL).rstrip("/")
        self._api_key = api_key
        self.model = model
        self.provider_name = provider_name
        self.connect_timeout = max(1.0, float(connect_timeout))
        self.read_timeout = max(1.0, float(read_timeout))
        self.max_retries = max(0, min(3, int(max_retries)))
        if media_root is not None:
            self.media_root = Path(media_root)
        else:
            self.media_root = Path(
                os.environ.get(_MEDIA_ROOT_ENV, "media")
            )
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.transport = transport or MiniMaxHttpTransport()
        self._health_status: str = "configured"
        self.last_run_metadata: dict[str, object] = {}

    # ------------------------------------------------------------------ #
    # Public provider protocol
    # ------------------------------------------------------------------ #

    def capabilities(self) -> MusicProviderCapabilities:
        return MusicProviderCapabilities(
            max_duration_seconds=MAX_DURATION_SECONDS,
            supports_progress=False,
            supports_cancel=False,
            supported_instruments=list(REFERENCE_INSTRUMENTS),
            supported_formats=["mp3", "wav"],
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
                max_input_characters=MINIMAX_PROMPT_MAX_LENGTH,
            ),
            safe_message=safe_message,
        )

    def create_task(self, request: ProviderMusicRequest) -> ProviderTask:
        validate_provider_request_capabilities(request, self.capabilities())
        started = time.perf_counter()
        prompt = _build_prompt(request)
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "is_instrumental": True,
                "lyrics_optimizer": False,
                "stream": False,
                "output_format": "hex",
                "audio_setting": {
                    "format": request.output_format,
                    "sample_rate": 44100,
                    "bitrate": 256000,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{MINIMAX_MUSIC_PATH}"
        last_error: MusicProviderFailureV3 | None = None
        for attempt in range(self.max_retries + 1):
            try:
                raw = self.transport(url, headers, body, self.read_timeout)
                return self._parse_completed_response(
                    raw=raw,
                    request=request,
                    started=started,
                    attempt=attempt + 1,
                )
            except MusicProviderFailureV3 as error:
                if error.retryable and attempt < self.max_retries:
                    last_error = error
                    time.sleep(min(2 ** attempt, 2.0))
                    continue
                self._record_failure(error, started, attempt + 1)
                raise error from None
            except BaseException as exc:  # transport-level failures
                error = self._classify_transport_error(exc)
                if error.retryable and attempt < self.max_retries:
                    last_error = error
                    time.sleep(min(2 ** attempt, 2.0))
                    continue
                self._record_failure(error, started, attempt + 1)
                raise error from exc
        if last_error is not None:
            raise last_error
        raise AssertionError("provider retry loop exhausted")

    def get_task(self, provider_task_id: str) -> ProviderTask:
        # REAL_SMOKE_REQUIRED: the documented MiniMax Music surface has no
        # query endpoint. We refuse to invent one: poll attempts are an
        # explicit provider failure and never a fake terminal success.
        raise MusicProviderFailureV3(
            "GENERATION_PROVIDER_UNAVAILABLE",
            retryable=True,
            safe_message="当前音乐生成服务不支持任务轮询。",
        )

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        # MiniMax Music documents no cancellation surface; report honest
        # capability instead of pretending the request was cancelled.
        raise MusicProviderFailureV3(
            "GENERATION_CANCEL_UNSUPPORTED",
            retryable=False,
            safe_message="当前生成服务不支持取消任务。",
        )

    # ---------------------------------------------------------------- #
    # Async protocol (to_thread on the same safe sync implementation)
    # ---------------------------------------------------------------- #

    async def acreate_task(self, request: ProviderMusicRequest) -> ProviderTask:
        return await asyncio.to_thread(self.create_task, request)

    async def aget_task(self, provider_task_id: str) -> ProviderTask:
        return self.get_task(provider_task_id)

    async def acancel_task(self, provider_task_id: str) -> ProviderTask:
        return self.cancel_task(provider_task_id)

    # ------------------------------------------------------------------ #
    # MiniMax response handling
    # ------------------------------------------------------------------ #

    def _parse_completed_response(
        self,
        *,
        raw: bytes,
        request: ProviderMusicRequest,
        started: float,
        attempt: int,
    ) -> ProviderTask:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise self._public_failure(
                "GENERATION_PROVIDER_REJECTED",
                cause=exc,
            ) from exc
        if not isinstance(payload, Mapping):
            raise self._public_failure(
                "GENERATION_PROVIDER_REJECTED",
                cause=ValueError("miniMax response is not an object"),
            )
        base_resp = payload.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        vendor_message = base_resp.get("status_msg")
        if status_code is not None and status_code != 0:
            code = _MINIMAX_STATUS_CODE_MAP.get(
                int(status_code), "GENERATION_PROVIDER_REJECTED"
            )
            error = self._public_failure(code, cause=ValueError(vendor_message or "miniMax error"))
            self._record_failure(error, started, attempt)
            raise error from None
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise self._public_failure(
                "GENERATION_PROVIDER_REJECTED",
                cause=ValueError("miniMax data missing"),
            )
        status = data.get("status")
        if status == 1:
            # In-progress create response. The documented API provides no
            # music poll handle, so we fail closed (explicit retryable failure)
            # instead of pretending a success we cannot later materialize.
            # REAL_SMOKE_REQUIRED: confirm whether the vendor may return
            # status=1 with a retrievable task handle and, if so, wire polling.
            error = self._public_failure(
                "GENERATION_PROVIDER_UNAVAILABLE",
                cause=ValueError("miniMax returned in-progress without a poll handle"),
            )
            self._record_failure(error, started, attempt)
            raise error from None
        audio_hex = data.get("audio")
        if status != 2 or not isinstance(audio_hex, str) or not audio_hex.strip():
            raise self._public_failure(
                "GENERATION_PROVIDER_REJECTED",
                cause=ValueError("miniMax success without audio payload"),
            )
        locator = self._materialize_audio(audio_hex, request.output_format)
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        self._health_status = "healthy"
        self.last_run_metadata = {
            "provider": self.provider_name,
            "model": self.model,
            "attempts": attempt,
            "latency_ms": latency_ms,
            "error_code": None,
            "trace_id": payload.get("trace_id"),
        }
        return ProviderTask(
            provider_task_id=_safe_provider_task_id(
                str(payload.get("trace_id") or ""), "minimax"
            ),
            status="succeeded",
            progress_value=100,
            asset_locator=locator,
            error_code=None,
        )

    def _materialize_audio(self, audio_hex: str, output_format: str) -> str:
        """Decode hex audio into the owned media root; never the vendor URL."""
        hex_body = audio_hex.strip()
        if hex_body.lower().startswith("0x"):
            hex_body = hex_body[2:]
        try:
            payload = bytes.fromhex(hex_body)
        except ValueError as exc:
            raise self._public_failure(
                "GENERATION_PROVIDER_REJECTED",
                cause=exc,
            ) from exc
        if not _looks_like_audio(payload):
            raise self._public_failure(
                "GENERATION_PROVIDER_REJECTED",
                cause=ValueError("miniMax audio payload is empty or not mp3/wav"),
            )
        file_name = f"{sha256(payload).hexdigest()[:16]}.{output_format}"
        target_dir = self.media_root / _GENERATED_SUBDIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file_name
        target.write_bytes(payload)
        return str(target.resolve())

    # ------------------------------------------------------------------ #
    # Error classification helpers
    # ------------------------------------------------------------------ #

    def _public_failure(
        self,
        error_code: str,
        *,
        cause: BaseException | None = None,
    ) -> MusicProviderFailureV3:
        normalized, message, retryable = _ERROR_MAPPING.get(
            error_code, _ERROR_MAPPING["GENERATION_PROVIDER_UNAVAILABLE"]
        )
        return MusicProviderFailureV3(
            normalized,
            retryable=retryable,
            safe_message=message,
            cause=cause,
        )

    def _classify_transport_error(
        self, exc: BaseException
    ) -> MusicProviderFailureV3:
        if isinstance(exc, HTTPError):
            if exc.code == 429:
                return self._public_failure(
                    "GENERATION_PROVIDER_RATE_LIMITED", cause=exc
                )
            if exc.code in {401, 403}:
                return self._public_failure(
                    "GENERATION_PROVIDER_AUTH_FAILED", cause=exc
                )
            if 500 <= exc.code <= 599:
                return self._public_failure(
                    "GENERATION_PROVIDER_UNAVAILABLE", cause=exc
                )
            return self._public_failure(
                "GENERATION_PROVIDER_REJECTED", cause=exc
            )
        if isinstance(exc, (ConnectionTimeoutError, ReadTimeoutError, TimeoutError)):
            return self._public_failure("GENERATION_PROVIDER_TIMEOUT", cause=exc)
        if isinstance(exc, OSError):
            return self._public_failure(
                "GENERATION_PROVIDER_UNAVAILABLE", cause=exc
            )
        return self._public_failure("GENERATION_PROVIDER_UNAVAILABLE", cause=exc)

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
        # Do not store raw vendor causes (may contain credentials).
        self._health_status = "degraded" if error.retryable else "down"

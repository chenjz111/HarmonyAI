"""Agent 4 — Tencent Cloud TokenHub / MiniMax Music adapter (official provider).

Owner decision for PR #120:

  Provider : Tencent Cloud TokenHub / MiniMax
  Endpoint : https://tokenhub.tencentmaas.com/v1/wand/minimax-music/generation
  Model    : minimax-music-v3.0
  Key      : TOKENHUB_API_KEY (environment only)

Design boundaries
-----------------
* JSON request (``application/json``): model / prompt / is_instrumental=true /
  output_format (url preferred, hex fully supported) / audio_setting.format=mp3.
  TokenHub / MiniMax music has NO duration parameter: ``spec.duration_seconds``
  is written into the prompt as a TARGET only, and the persisted duration is the
  measured length of the saved audio.
* Rule-asset compatibility: Chinese instrument values (古琴/箫/琵琶/笛/埙) are
  normalized to provider tokens for validation and the prompt; the original
  values stay in the request/persistence for display. Unmapped instruments fail
  explicitly. The "无额外环境音" ambient value never becomes a prompt fragment —
  the ambience sentence is omitted instead.
* The generation POST is executed EXACTLY ONCE — automatic retry is 0 — so a
  transient failure can never cause a duplicate paid generation. Idempotency is
  the service layer's job (Idempotency-Key).
* Both response shapes are handled and materialized into the project-owned media
  root before success is reported:
    - ``data.audio`` as hex  -> decoded and saved as MP3;
    - ``data.audio`` as URL  -> downloaded immediately (provider links are
      short-lived) and saved as an owned asset. The temporary provider URL is
      never stored in the database, task payload or Player stream.
* ``extra_info.music_duration`` is milliseconds and is converted to seconds for
  the ops-internal run metadata (the persisted asset duration remains the
  measured duration of the saved file).
* The direct MiniMax endpoint ``https://api.minimax.io/v1/music_generation`` is
  forbidden for this sprint and is never called by this adapter or the bundle
  builder (regression-tested).
* Failures (missing key/permission/balance/timeout/5xx/empty audio) surface as
  explicit stable failures; Real mode never switches to Mock and never pretends
  a generated success.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import os
from pathlib import Path
import re
import time
from typing import Protocol
from urllib.parse import urljoin, urlsplit

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

TOKENHUB_DEFAULT_BASE_URL = "https://tokenhub.tencentmaas.com"
TOKENHUB_MUSIC_PATH = "/v1/wand/minimax-music/generation"
DEFAULT_TOKENHUB_MUSIC_MODEL = "minimax-music-v3.0"

# The direct MiniMax endpoint must never be used for Sprint 5.
FORBIDDEN_MINIMAX_BASE_URL = "https://api.minimax.io"
FORBIDDEN_MINIMAX_PATH = "/v1/music_generation"

# Duration envelope per the MiniMax music class used by the app (10-300 s).
# REAL_SMOKE_REQUIRED: record the exact provider envelope after Owner smoke.
# Project-internal upper bound for a single generation (seconds). This is NOT a
# provider-confirmed capability: TokenHub / MiniMax music takes the length from
# the prompt only, so the real envelope is recorded after the Owner smoke.
PROJECT_INTERNAL_MAX_DURATION_SECONDS = 300
TOKENHUB_MAX_DURATION_SECONDS = PROJECT_INTERNAL_MAX_DURATION_SECONDS

# Hard cap for provider audio payloads (hex or downloaded URL), 25 MiB.
TOKENHUB_MAX_AUDIO_BYTES = 25 * 1024 * 1024

TOKENHUB_PROMPT_MAX_LENGTH = 2000

# Fixed rule-asset -> provider token mapping. Rule assets publish Chinese
# instrument names (used unchanged for the five-tone analysis page display);
# the provider prompt uses the normalized token only.
INSTRUMENT_ALIASES: dict[str, str] = {
    "古琴": "guqin",
    "箫": "xiao",
    "琵琶": "pipa",
    "笛": "dizi",
    "埙": "xun",
    # canonical tokens are accepted as-is
    "guqin": "guqin",
    "xiao": "xiao",
    "pipa": "pipa",
    "dizi": "dizi",
    "xun": "xun",
}

# Instruments the TokenHub adapter can render (normalized provider tokens).
SUPPORTED_INSTRUMENTS: tuple[str, ...] = ("guqin", "xiao", "pipa", "dizi", "xun")
# Backwards-compatible alias for older references/tests.
REFERENCE_INSTRUMENTS = SUPPORTED_INSTRUMENTS

# Ambient values that mean "no extra ambient sound": they must never be rendered
# as "soft 无额外环境音 ambience" and the ambience sentence is omitted instead.
NO_AMBIENT_TOKENS: frozenset[str] = frozenset(
    {
        "无额外环境音",
        "无其他环境音",
        "无环境音",
        "无",
        "不需要",
        "none",
        "no_extra_ambient",
        "no_ambient",
    }
)

_TONE_MOOD = {
    "gong": "steady, grounded, calm earth energy",
    "shang": "clear, bright metal energy",
    "jiao": "gentle, flowing wood energy",
    "zhi": "warm, radiant fire energy",
    "yu": "fluid, deep water energy",
}

_MEDIA_ROOT_ENV = "HARMONY_MEDIA_ROOT"
_GENERATED_SUBDIR = Path("generated") / "tokenhub"

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

# TokenHub / MiniMax base_resp.status_code -> stable public error code.
_STATUS_CODE_MAP = {
    0: None,
    1002: "GENERATION_PROVIDER_RATE_LIMITED",
    1004: "GENERATION_PROVIDER_AUTH_FAILED",
    1008: "GENERATION_PROVIDER_REJECTED",  # insufficient balance
    1026: "GENERATION_PROVIDER_REJECTED",  # content flagged
    2013: "GENERATION_PROVIDER_REJECTED",  # invalid parameters
    2049: "GENERATION_PROVIDER_AUTH_FAILED",
}


class TokenHubResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    text: str


class TokenHubPoster(Protocol):
    def __call__(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json_payload: dict[str, object],
        timeout: tuple[float, float],
    ) -> TokenHubResponse: ...


@dataclass(frozen=True)
class DownloadedAudio:
    """Downloaded audio bytes plus the final (post-redirect) URL."""

    content: bytes
    final_url: str


class AudioDownloadTooLarge(RuntimeError):
    """Raised when a provider audio payload exceeds the configured cap."""


class UnsafeAudioRedirect(RuntimeError):
    """Raised when a redirect target is not a public HTTPS address."""


class TooManyAudioRedirects(RuntimeError):
    """Raised when the audio redirect chain exceeds the allowed hop count."""


# Audio downloads follow redirects manually so every hop is validated first.
MAX_AUDIO_REDIRECTS = 3
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class TokenHubDownloader(Protocol):
    def __call__(
        self, url: str, *, timeout: tuple[float, float], max_bytes: int
    ) -> DownloadedAudio: ...


def _requests_poster(
    url: str,
    *,
    headers: dict[str, str],
    json_payload: dict[str, object],
    timeout: tuple[float, float],
) -> TokenHubResponse:
    """Default JSON poster; requests sets Content-Type: application/json."""
    return requests.post(
        url, headers=headers, json=json_payload, timeout=timeout
    )  # type: ignore[return-value]


def _requests_downloader(
    url: str, *, timeout: tuple[float, float], max_bytes: int
) -> DownloadedAudio:
    """Hop-by-hop HTTPS download: validate every redirect before following it.

    ``allow_redirects=False`` guarantees we never follow an unvalidated hop; each
    Location target must be a public HTTPS URL, the hop count is bounded, the
    payload is streamed with a hard size cap.
    """
    current = url
    for hop in range(MAX_AUDIO_REDIRECTS + 1):
        if not _is_public_https_url(current):
            raise UnsafeAudioRedirect(f"unsafe audio URL at hop {hop}")
        with requests.get(
            current, timeout=timeout, stream=True, allow_redirects=False
        ) as response:
            status = int(getattr(response, "status_code", 0))
            if status in _REDIRECT_STATUSES:
                location = (getattr(response, "headers", {}) or {}).get("location")
                if not location:
                    raise UnsafeAudioRedirect("redirect without Location header")
                target = urljoin(current, str(location))
                if not _is_public_https_url(target):
                    # never follow a hop to HTTP / localhost / private / link-local
                    raise UnsafeAudioRedirect("redirect target is not public HTTPS")
                if hop >= MAX_AUDIO_REDIRECTS:
                    raise TooManyAudioRedirects(
                        f"more than {MAX_AUDIO_REDIRECTS} audio redirects"
                    )
                current = target
                continue

            response.raise_for_status()
            final_url = str(getattr(response, "url", "") or current)
            if not _is_public_https_url(final_url):
                raise UnsafeAudioRedirect("final audio URL is not public HTTPS")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise AudioDownloadTooLarge(
                        f"provider audio payload exceeds {max_bytes} bytes"
                    )
                chunks.append(chunk)
            return DownloadedAudio(content=b"".join(chunks), final_url=final_url)
    raise TooManyAudioRedirects(f"more than {MAX_AUDIO_REDIRECTS} audio redirects")


def _is_public_https_url(url: str) -> bool:
    """Allow only public HTTPS URLs (no HTTP, loopback, private, link-local)."""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return False
    if parsed.scheme.lower() != "https":
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    host = hostname.strip().lower().rstrip(".")
    if host in {"localhost", "0.0.0.0"} or host.endswith(
        (".localhost", ".local", ".internal", ".localdomain")
    ):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True  # a normal DNS name
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _normalize_base_url(value: str) -> str:
    return (value or "").strip().rstrip("/").lower()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def milliseconds_to_seconds(value: int | float) -> float:
    """Convert provider ``music_duration`` (milliseconds) to seconds."""
    return float(value) / 1000.0


def normalize_instrument(value: str) -> str:
    """Map a rule-asset instrument value to the provider token.

    Chinese names published by the rule assets are supported for the five fixed
    instruments; anything unmapped fails explicitly (never silently dropped).
    """
    key = str(value).strip()
    token = INSTRUMENT_ALIASES.get(key)
    if token is None:
        raise MusicProviderFailureV3(
            "GENERATION_INSTRUMENT_UNSUPPORTED",
            retryable=False,
            safe_message="当前生成服务不支持所需乐器（存在未映射的乐器值）。",
        )
    return token


def normalize_instruments(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        token = normalize_instrument(value)
        if token not in seen:
            seen.append(token)
    return seen


def _ambient_prompt_parts(ambient_sounds: list[str]) -> list[str]:
    """Render real ambience only; 'no extra ambient' never becomes a prompt."""
    parts: list[str] = []
    for item in ambient_sounds:
        token = str(item).strip()
        if not token:
            continue
        if token in NO_AMBIENT_TOKENS or token.lower() in NO_AMBIENT_TOKENS:
            continue
        parts.append(f"soft {token} ambience")
    return parts


def _build_prompt(request: ProviderMusicRequest, *, instruments: list[str]) -> str:
    """Deterministic, medical-neutral instrumental prompt from the spec.

    ``instruments`` must already be normalized provider tokens; the spec keeps
    the rule-asset (Chinese) values for display. ``duration_seconds`` is only a
    prompt-level TARGET — TokenHub / MiniMax music has no duration parameter.
    """
    spec = request.generation_spec
    tone_profile = spec.tone_profile
    tone = getattr(tone_profile, "dominant_tone", None) if tone_profile else None
    rendered_instruments = ", ".join(instruments) or "warm acoustic textures"
    ambient_parts = _ambient_prompt_parts(spec.ambient_sounds)
    structure = spec.structure
    parts = ["Traditional Chinese instrumental healing music"]
    if tone:
        mood = _TONE_MOOD.get(tone, "steady, calm")
        parts.append(f"in {tone} mode ({mood})")
    parts.extend(
        [
            f"bpm {spec.bpm}",
            f"target length about {spec.duration_seconds} seconds",
            f"Instruments: {rendered_instruments}",
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
    if len(prompt) > TOKENHUB_PROMPT_MAX_LENGTH:
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


def _is_http_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _safe_provider_task_id(*candidates: object) -> str:
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        sanitized = re.sub(r"[^A-Za-z0-9_-]", "", candidate)
        if sanitized:
            return sanitized[:64]
    return "tokenhub"


class TokenHubMinimaxMusicProvider:
    """TokenHub / MiniMax music adapter behind the frozen provider protocol."""

    provider_name = "tokenhub"
    # explicit ops-internal audit label recorded on generation_tasks.provider
    provider_audit_label = "tokenhub/minimax-music-v3.0"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_TOKENHUB_MUSIC_MODEL,
        base_url: str = TOKENHUB_DEFAULT_BASE_URL,
        media_root: str | os.PathLike[str] | None = None,
        connect_timeout: float = 20.0,
        read_timeout: float = 300.0,
        max_download_bytes: int = TOKENHUB_MAX_AUDIO_BYTES,
        poster: TokenHubPoster | None = None,
        downloader: TokenHubDownloader | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="音乐生成服务尚未配置。",
            )
        if not model or model.strip() != DEFAULT_TOKENHUB_MUSIC_MODEL:
            # Exact model match only: no prefix matching, no model drift.
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message=(
                    "TokenHub 音乐模型配置无效（必须精确为 "
                    f"{DEFAULT_TOKENHUB_MUSIC_MODEL}）。"
                ),
            )
        resolved_base = (base_url or TOKENHUB_DEFAULT_BASE_URL).strip().rstrip("/")
        normalized_base = _normalize_base_url(resolved_base)
        if normalized_base == _normalize_base_url(FORBIDDEN_MINIMAX_BASE_URL):
            # Hard guard: the direct MiniMax endpoint is not allowed in Sprint 5.
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message="音乐生成服务配置错误（禁止直连 api.minimax.io）。",
            )
        if normalized_base != _normalize_base_url(TOKENHUB_DEFAULT_BASE_URL):
            # Strict allow-list: the API key must only ever be sent to the
            # official TokenHub host, never to an arbitrary BASE_URL value.
            raise MusicProviderFailureV3(
                "PROVIDER_NOT_CONFIGURED",
                retryable=False,
                safe_message=(
                    "音乐生成服务配置错误（TOKENHUB_BASE_URL 必须为官方 "
                    f"{TOKENHUB_DEFAULT_BASE_URL}）。"
                ),
            )
        self._api_key = api_key
        self.model = model.strip()
        self.base_url = resolved_base
        self.connect_timeout = max(1.0, float(connect_timeout))
        self.read_timeout = max(10.0, float(read_timeout))
        self.max_download_bytes = max(1, int(max_download_bytes))
        if media_root is not None:
            self.media_root = Path(media_root)
        else:
            self.media_root = Path(os.environ.get(_MEDIA_ROOT_ENV, "media"))
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.poster = poster or _requests_poster
        self.downloader = downloader or _requests_downloader
        self._health_status: str = "configured"
        self.last_run_metadata: dict[str, object] = {}
        self.post_calls = 0
        self.download_calls = 0

    # ------------------------------------------------------------------ #
    # Provider protocol
    # ------------------------------------------------------------------ #

    def capabilities(self) -> MusicProviderCapabilities:
        return MusicProviderCapabilities(
            # project-internal upper bound, not a provider-confirmed capability
            max_duration_seconds=PROJECT_INTERNAL_MAX_DURATION_SECONDS,
            supports_progress=False,
            supports_cancel=False,
            supported_instruments=list(SUPPORTED_INSTRUMENTS),
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
                max_input_characters=TOKENHUB_PROMPT_MAX_LENGTH,
            ),
            safe_message=safe_message,
        )

    def create_task(self, request: ProviderMusicRequest) -> ProviderTask:
        # Rule assets publish Chinese instrument names; normalize to provider
        # tokens for capability validation and the prompt only. The request (and
        # therefore persistence/read model) keeps the original values.
        normalized_instruments = normalize_instruments(
            list(request.generation_spec.instruments)
        )
        normalized_spec = request.generation_spec.model_copy(
            update={"instruments": normalized_instruments}
        )
        normalized_request = request.model_copy(
            update={"generation_spec": normalized_spec}
        )
        validate_provider_request_capabilities(normalized_request, self.capabilities())
        started = time.perf_counter()
        prompt = _build_prompt(request, instruments=normalized_instruments)
        # NOTE: TokenHub / MiniMax music has NO duration request parameter.
        # spec.duration_seconds is a prompt-level target only; the persisted
        # duration comes from measuring the saved audio after success.
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "is_instrumental": True,
            "output_format": "url",
            "audio_setting": {"format": "mp3"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self.base_url}{TOKENHUB_MUSIC_PATH}"

        # REAL RULE: exactly one generation POST; automatic retry is 0.
        self.post_calls += 1
        try:
            response = self.poster(
                url,
                headers=headers,
                json_payload=payload,
                timeout=(self.connect_timeout, self.read_timeout),
            )
        except BaseException as exc:
            error = self._classify_transport_error(exc)
            self._record_failure(error, started, 1)
            raise error from exc

        task = self._parse_response(response=response, started=started)
        if task.status == "succeeded":
            self._health_status = "healthy"
        return task

    def get_task(self, provider_task_id: str) -> ProviderTask:
        # TokenHub music generation is synchronous; no documented query surface.
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
        self, *, response: TokenHubResponse, started: float
    ) -> ProviderTask:
        status_code = int(getattr(response, "status_code", 0))
        if status_code != 200:
            error = self._public_failure(self._map_http_status(status_code))
            self._record_failure(error, started, 1)
            raise error from None

        payload = self._decode_json(response)
        base_resp = payload.get("base_resp") or {}
        provider_code = (
            base_resp.get("status_code") if isinstance(base_resp, Mapping) else None
        )
        if provider_code not in (None, 0):
            code = _STATUS_CODE_MAP.get(
                int(provider_code), "GENERATION_PROVIDER_REJECTED"
            )
            error = self._public_failure(code)
            self._record_failure(error, started, 1)
            raise error from None

        data = payload.get("data")
        if not isinstance(data, Mapping):
            error = self._public_failure("GENERATION_PROVIDER_REJECTED")
            self._record_failure(error, started, 1)
            raise error from None

        data_status = data.get("status")
        if data_status == 1:
            # In-progress create response without a documented poll handle:
            # fail closed instead of pretending success we cannot materialize.
            error = self._public_failure("GENERATION_PROVIDER_UNAVAILABLE")
            self._record_failure(error, started, 1)
            raise error from None

        audio_ref = data.get("audio")
        if data_status != 2 or not isinstance(audio_ref, str) or not audio_ref.strip():
            error = self._public_failure("GENERATION_PROVIDER_REJECTED")
            self._record_failure(error, started, 1)
            raise error from None

        try:
            locator = self._materialize_audio(audio_ref)
        except MusicProviderFailureV3 as error:
            self._record_failure(error, started, 1)
            raise

        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        extra_info = payload.get("extra_info") or {}
        music_duration_ms = (
            extra_info.get("music_duration")
            if isinstance(extra_info, Mapping)
            else None
        )
        usage = payload.get("usage") or {}
        total_tokens = usage.get("total_tokens") if isinstance(usage, Mapping) else None
        self.last_run_metadata = {
            "provider": self.provider_name,
            "provider_label": self.provider_audit_label,
            "model": self.model,
            "attempts": 1,
            "latency_ms": latency_ms,
            "error_code": None,
            "trace_id": payload.get("trace_id"),
            "request_id": payload.get("request_id"),
            "total_tokens": total_tokens,
            "provider_reported_duration_ms": music_duration_ms,
            "provider_reported_duration_seconds": (
                milliseconds_to_seconds(music_duration_ms)
                if isinstance(music_duration_ms, (int, float))
                else None
            ),
        }
        return ProviderTask(
            provider_task_id=_safe_provider_task_id(
                payload.get("trace_id"),
                payload.get("request_id"),
                str(payload.get("id") or ""),
            ),
            status="succeeded",
            progress_value=100,
            asset_locator=locator,
            error_code=None,
        )

    @staticmethod
    def _decode_json(response: TokenHubResponse) -> Mapping[str, object]:
        try:
            payload = json.loads(getattr(response, "text", "") or "")
        except (ValueError, TypeError) as exc:
            raise MusicProviderFailureV3(
                "GENERATION_PROVIDER_REJECTED",
                retryable=False,
                safe_message="音乐生成服务返回了无效结果。",
                cause=exc,
            ) from exc
        if not isinstance(payload, Mapping):
            raise MusicProviderFailureV3(
                "GENERATION_PROVIDER_REJECTED",
                retryable=False,
                safe_message="音乐生成服务返回了无效结果。",
            )
        return payload

    def _reject_audio(self, message: str, cause: BaseException | None = None) -> MusicProviderFailureV3:
        return MusicProviderFailureV3(
            "GENERATION_PROVIDER_REJECTED",
            retryable=False,
            safe_message=message,
            cause=cause,
        )

    def _materialize_audio(self, audio_ref: str) -> str:
        """Store owned MP3 bytes for a hex payload or a short-lived provider URL.

        URL policy (Owner hardening): HTTPS only, public host only, hard size
        cap, final post-redirect URL re-checked, MP3 validated after download.
        The temporary provider URL is never returned or persisted.
        """
        if _is_http_url(audio_ref):
            candidate = audio_ref.strip()
            if not _is_public_https_url(candidate):
                raise self._reject_audio(
                    "音乐生成服务返回的音频地址不安全（仅允许公共 HTTPS 地址）。"
                )
            self.download_calls += 1
            try:
                downloaded = self.downloader(
                    candidate,
                    timeout=(self.connect_timeout, self.read_timeout),
                    max_bytes=self.max_download_bytes,
                )
            except AudioDownloadTooLarge as exc:
                raise self._reject_audio("音乐生成服务返回的音频过大，已拒绝。", exc) from exc
            except (UnsafeAudioRedirect, TooManyAudioRedirects) as exc:
                raise self._reject_audio(
                    "音乐生成服务音频地址跳转不安全或次数过多，已拒绝。", exc
                ) from exc
            except requests.TooManyRedirects as exc:
                raise self._reject_audio(
                    "音乐生成服务音频地址跳转过多，已拒绝。", exc
                ) from exc
            except MusicProviderFailureV3:
                raise
            except BaseException as exc:
                raise self._classify_transport_error(exc) from exc

            if isinstance(downloaded, (bytes, bytearray)):
                payload = bytes(downloaded)
                final_url = candidate
            else:
                payload = downloaded.content
                final_url = downloaded.final_url or candidate
            if not _is_public_https_url(final_url):
                raise self._reject_audio(
                    "音乐生成服务音频地址跳转不安全（仅允许公共 HTTPS）。"
                )
            if len(payload) > self.max_download_bytes:
                raise self._reject_audio("音乐生成服务返回的音频过大，已拒绝。")
        else:
            hex_body = audio_ref.strip()
            if hex_body.lower().startswith("0x"):
                hex_body = hex_body[2:]
            try:
                payload = bytes.fromhex(hex_body)
            except ValueError as exc:
                raise self._reject_audio("音乐生成服务返回了无效音频。", exc) from exc
            if len(payload) > self.max_download_bytes:
                raise self._reject_audio("音乐生成服务返回的音频过大，已拒绝。")

        if not _looks_like_mp3(payload):
            raise self._reject_audio("音乐生成服务未返回可播放音频。")

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

    def _classify_transport_error(self, exc: BaseException) -> MusicProviderFailureV3:
        if isinstance(exc, (requests.Timeout, TimeoutError)):
            return self._public_failure("GENERATION_PROVIDER_TIMEOUT")
        if isinstance(exc, requests.HTTPError):
            status = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            return self._public_failure(self._map_http_status(status) if status else "GENERATION_PROVIDER_REJECTED")
        if isinstance(exc, (requests.RequestException, OSError)):
            return self._public_failure("GENERATION_PROVIDER_UNAVAILABLE")
        return self._public_failure("GENERATION_PROVIDER_UNAVAILABLE")

    def _record_failure(
        self, error: MusicProviderFailureV3, started: float, attempt: int
    ) -> None:
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        self.last_run_metadata = {
            "provider": self.provider_name,
            "provider_label": self.provider_audit_label,
            "model": self.model,
            "attempts": attempt,
            "latency_ms": latency_ms,
            "error_code": error.error_code,
        }
        # Raw vendor message/body is intentionally never stored (secret risk).
        self._health_status = "degraded" if error.retryable else "down"

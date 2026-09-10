"""Tencent Cloud TokenHub / MiniMax music adapter — real mode, fail-closed.

Covers the Owner-mandated checks: JSON request shape, single POST with
automatic retry 0, hex save, URL download save, ms->s duration conversion,
error mapping (HTTP + base_resp), secret non-leakage, and the forbidden
``https://api.minimax.io/v1/music_generation`` endpoint guard.
"""

import asyncio
import json
from pathlib import Path

import pytest
import requests

from backend.ai_engine.v3.generation_provider_adapter import (
    NotConfiguredMusicProvider,
    build_music_provider_bundle,
)
from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.ai_engine.v3 import tokenhub_minimax_music_provider as tokenhub_module
from backend.ai_engine.v3.tokenhub_minimax_music_provider import (
    DEFAULT_TOKENHUB_MUSIC_MODEL,
    FORBIDDEN_MINIMAX_BASE_URL,
    INSTRUMENT_ALIASES,
    PROJECT_INTERNAL_MAX_DURATION_SECONDS,
    SUPPORTED_INSTRUMENTS,
    TOKENHUB_DEFAULT_BASE_URL,
    TOKENHUB_MAX_DURATION_SECONDS,
    TOKENHUB_MUSIC_PATH,
    AudioDownloadTooLarge,
    DownloadedAudio,
    TokenHubMinimaxMusicProvider,
    milliseconds_to_seconds,
    normalize_instrument,
    normalize_instruments,
)
from backend.app.schemas.v3.music import (
    MusicProviderCapabilities,
    ProviderMusicRequest,
    ProviderTask,
)

TEST_KEY = "tk-test-tokenhub-secret"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _tone_profile() -> dict[str, object]:
    return {
        "schema_version": "tone_profile_v3.0",
        "status": "available",
        "weights": {"jiao": 0.2, "zhi": 0.2, "gong": 0.2, "shang": 0.2, "yu": 0.2},
        "dominant_tone": "gong",
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {"diagnosis_id": "diag_test", "supporting_fact_ids": []},
    }


def _generation_spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 60,
        "instruments": ["guqin", "xiao"],
        "ambient_sounds": ["water"],
        "structure": {"intro_seconds": 6, "main_seconds": 48, "outro_seconds": 6},
        "energy_curve": "gentle_decline",
        "forbidden_constraints": ["sharp_high_frequency"],
        "fallback_policy": {"allow_local_matching": True},
    }


def _request(
    *,
    instruments: list[str] | None = None,
    ambient: list[str] | None = None,
    duration_seconds: int | None = None,
) -> ProviderMusicRequest:
    spec: dict[str, object] = dict(_generation_spec())
    if instruments is not None:
        spec["instruments"] = instruments
    if ambient is not None:
        spec["ambient_sounds"] = ambient
    if duration_seconds is not None:
        spec["duration_seconds"] = duration_seconds
        spec["structure"] = {
            "intro_seconds": 6,
            "main_seconds": duration_seconds - 12,
            "outro_seconds": 6,
        }
    return ProviderMusicRequest(
        provider_request_id="pr_tokenhub_test",
        generation_spec=spec,  # type: ignore[arg-type]
        output_format="mp3",
        callback_ref=None,
    )


def mp3_bytes(*, seconds: float = 3.0) -> bytes:
    """Deterministic MPEG1 Layer III 128 kbps 44.1 kHz stream."""
    bitrate_kbps = 128
    samplerate = 44100
    samples_per_frame = 1152
    frame_length = int(samples_per_frame * bitrate_kbps * 1000 / (8 * samplerate))
    frame = b"\xff\xfb\x90\x00" + bytes(max(0, frame_length - 4))
    frames = max(1, int(seconds * samplerate / samples_per_frame) + 1)
    return frame * frames


def _completed_body(
    audio_ref: str,
    *,
    music_duration_ms: int | None = 25364,
    trace_id: object = "trace-tokenhub-1",
    request_id: object = "req-tokenhub-1",
    total_tokens: object = 1234,
    base_status: int = 0,
) -> str:
    payload: dict[str, object] = {
        "data": {"status": 2, "audio": audio_ref},
        "base_resp": {"status_code": base_status, "status_msg": "success"},
    }
    if trace_id is not None:
        payload["trace_id"] = trace_id
    if request_id is not None:
        payload["request_id"] = request_id
    if total_tokens is not None:
        payload["usage"] = {"total_tokens": total_tokens}
    if music_duration_ms is not None:
        payload["extra_info"] = {"music_duration": music_duration_ms}
    return json.dumps(payload)


class FakeResponse:
    def __init__(self, *, status_code: int = 200, text: str = "", content_type: str = "application/json"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {"content-type": content_type}


class FakePoster:
    def __init__(self, response: FakeResponse | None = None, error: BaseException | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, url, *, headers, json_payload, timeout):
        self.calls.append(
            {"url": url, "headers": dict(headers), "json": dict(json_payload), "timeout": timeout}
        )
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake poster has no response")
        return self.response


class FakeDownloader:
    def __init__(
        self,
        payload: bytes | None = None,
        error: BaseException | None = None,
        *,
        final_url: str | None = None,
    ):
        self.payload = payload
        self.error = error
        self.final_url = final_url
        self.calls: list[str] = []
        self.max_bytes_seen: list[int] = []

    def __call__(self, url, *, timeout, max_bytes):
        self.calls.append(url)
        self.max_bytes_seen.append(max_bytes)
        if self.error is not None:
            raise self.error
        if self.payload is None:
            raise AssertionError("fake downloader has no payload")
        return DownloadedAudio(
            content=self.payload, final_url=self.final_url or url
        )


def _provider(
    tmp_path: Path, poster, downloader=None, *, base_url: str = TOKENHUB_DEFAULT_BASE_URL,
    max_download_bytes: int | None = None,
) -> TokenHubMinimaxMusicProvider:
    kwargs: dict[str, object] = {}
    if max_download_bytes is not None:
        kwargs["max_download_bytes"] = max_download_bytes
    return TokenHubMinimaxMusicProvider(
        api_key=TEST_KEY,
        model=DEFAULT_TOKENHUB_MUSIC_MODEL,
        base_url=base_url,
        media_root=tmp_path,
        poster=poster,
        downloader=downloader,
        **kwargs,  # type: ignore[arg-type]
    )


def _env(**overrides) -> dict[str, str]:
    env = {
        "MUSIC_PROVIDER": "tokenhub",
        "TOKENHUB_BASE_URL": TOKENHUB_DEFAULT_BASE_URL,
        "TOKENHUB_MUSIC_MODEL": DEFAULT_TOKENHUB_MUSIC_MODEL,
        "TOKENHUB_API_KEY": TEST_KEY,
        "HARMONY_MEDIA_ROOT": str(Path("unused")),
    }
    env.update(overrides)
    return env


# ------------------------------------------------------------------ bundle wiring


def test_tokenhub_env_builds_real_adapter(tmp_path):
    bundle = build_music_provider_bundle(_env(HARMONY_MEDIA_ROOT=str(tmp_path)))
    assert isinstance(bundle.provider, TokenHubMinimaxMusicProvider)
    assert bundle.provider.provider_name == "tokenhub"
    assert bundle.provider.provider_audit_label == "tokenhub/minimax-music-v3.0"
    assert bundle.provider.model == DEFAULT_TOKENHUB_MUSIC_MODEL
    assert bundle.provider.base_url == TOKENHUB_DEFAULT_BASE_URL
    assert bundle.health.status == "configured"
    serialized = bundle.health.model_dump_json()
    assert TEST_KEY not in serialized


def test_tokenhub_default_endpoint_is_official():
    bundle = build_music_provider_bundle(_env(TOKENHUB_BASE_URL=""))
    assert isinstance(bundle.provider, TokenHubMinimaxMusicProvider)
    assert bundle.provider.base_url == TOKENHUB_DEFAULT_BASE_URL
    assert "api.minimax.io" not in bundle.provider.base_url


def test_tokenhub_base_url_is_strictly_allow_listed(tmp_path):
    # A wrong TOKENHUB_BASE_URL must never send TOKENHUB_API_KEY elsewhere.
    with pytest.raises(MusicProviderFailureV3) as caught:
        _provider(tmp_path, FakePoster(), base_url="https://evil.example.com")
    assert caught.value.error_code == "PROVIDER_NOT_CONFIGURED"
    assert TEST_KEY not in str(caught.value)

    bundle = build_music_provider_bundle(
        _env(TOKENHUB_BASE_URL="https://evil.example.com", HARMONY_MEDIA_ROOT=str(tmp_path))
    )
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"
    assert bundle.health.safe_message is not None
    assert TOKENHUB_DEFAULT_BASE_URL in bundle.health.safe_message

    with pytest.raises(MusicProviderFailureV3):
        _provider(tmp_path, FakePoster(), base_url="http://tokenhub.tencentmaas.com")


def test_tokenhub_missing_key_keeps_readiness_not_configured(tmp_path):
    bundle = build_music_provider_bundle(_env(TOKENHUB_API_KEY="", HARMONY_MEDIA_ROOT=str(tmp_path)))
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.provider.provider_name == "tokenhub"
    assert bundle.health.status == "not_configured"
    with pytest.raises(MusicProviderFailureV3) as caught:
        bundle.provider.create_task(_request())
    assert caught.value.error_code == "PROVIDER_NOT_CONFIGURED"


def test_tokenhub_invalid_model_keeps_readiness_not_configured(tmp_path):
    for bad_model in ("gpt-4o", "minimax-music", "minimax-music-v3", "minimax-music-v3.1"):
        bundle = build_music_provider_bundle(
            _env(TOKENHUB_MUSIC_MODEL=bad_model, HARMONY_MEDIA_ROOT=str(tmp_path))
        )
        assert isinstance(bundle.provider, NotConfiguredMusicProvider), bad_model
        assert bundle.health.status == "not_configured", bad_model


def test_model_must_match_exactly(tmp_path):
    # prefix-but-not-exact models are rejected by the adapter itself too
    for bad_model in ("minimax-music-v3.1", "minimax-music", "minimax-music-v3.0-extra"):
        with pytest.raises(MusicProviderFailureV3) as caught:
            TokenHubMinimaxMusicProvider(
                api_key=TEST_KEY,
                model=bad_model,
                base_url=TOKENHUB_DEFAULT_BASE_URL,
                media_root=tmp_path,
            )
        assert caught.value.error_code == "PROVIDER_NOT_CONFIGURED"
    provider = _provider(tmp_path, FakePoster())
    assert provider.model == DEFAULT_TOKENHUB_MUSIC_MODEL


def test_stability_env_is_historical_unenabled(tmp_path):
    env = _env(MUSIC_PROVIDER="stability", HARMONY_MEDIA_ROOT=str(tmp_path))
    env["STABILITY_API_KEY"] = "sk-test-stability-secret"
    env["MUSIC_PROVIDER_MODEL"] = "stable-audio-2.5"
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"
    assert bundle.health.safe_message is not None
    assert "历史" in bundle.health.safe_message
    assert "TokenHub" in bundle.health.safe_message


def test_minimax_env_is_blocked_and_never_built(tmp_path):
    env = _env(MUSIC_PROVIDER="minimax", HARMONY_MEDIA_ROOT=str(tmp_path))
    env["MUSIC_PROVIDER_API_KEY"] = "sk-direct-minimax-secret"
    env["MUSIC_PROVIDER_MODEL"] = "music-3.0"
    env["MUSIC_PROVIDER_BASE_URL"] = "https://api.minimax.io"
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"
    assert bundle.health.safe_message is not None
    assert "BLOCKED_BY_PROVIDER_ENTITLEMENT" in bundle.health.safe_message


def test_forbidden_direct_minimax_endpoint_is_guarded(tmp_path):
    with pytest.raises(MusicProviderFailureV3) as caught:
        TokenHubMinimaxMusicProvider(
            api_key=TEST_KEY,
            base_url=FORBIDDEN_MINIMAX_BASE_URL,
            media_root=tmp_path,
        )
    assert caught.value.error_code == "PROVIDER_NOT_CONFIGURED"


# ------------------------------------------------------------- capability gates


def test_capabilities_are_honest():
    provider = _provider(Path("."), FakePoster())
    caps: MusicProviderCapabilities = provider.capabilities()
    assert caps.supports_progress is False
    assert caps.supports_cancel is False
    assert caps.max_duration_seconds == TOKENHUB_MAX_DURATION_SECONDS
    assert caps.supported_formats == ["mp3"]
    assert "guqin" in caps.supported_instruments


def test_duration_beyond_capability_rejected_before_any_call(tmp_path):
    request = _request().model_copy(deep=True)
    spec = request.generation_spec.model_copy(update={"duration_seconds": 900})
    request = request.model_copy(update={"generation_spec": spec})
    poster = FakePoster(response=FakeResponse(text=_completed_body(mp3_bytes().hex())))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(request)
    assert caught.value.error_code == "GENERATION_DURATION_UNSUPPORTED"
    assert poster.calls == []


# ------------------------------------------------------------------ hex success


def test_hex_response_is_decoded_saved_and_posts_exactly_once(tmp_path):
    audio = mp3_bytes(seconds=3)
    poster = FakePoster(response=FakeResponse(text=_completed_body(audio.hex())))
    provider = _provider(tmp_path, poster)
    task = provider.create_task(_request())

    assert isinstance(task, ProviderTask)
    assert task.status == "succeeded"
    assert task.progress_value == 100
    assert task.provider_task_id == "trace-tokenhub-1"
    stored = Path(task.asset_locator)
    assert stored.is_file() and stored.read_bytes() == audio
    assert "http" not in task.asset_locator

    assert len(poster.calls) == 1  # automatic retry is 0
    call = poster.calls[0]
    assert call["url"] == TOKENHUB_DEFAULT_BASE_URL + TOKENHUB_MUSIC_PATH
    assert call["headers"]["Authorization"] == f"Bearer {TEST_KEY}"
    body = call["json"]
    assert body["model"] == DEFAULT_TOKENHUB_MUSIC_MODEL
    assert body["is_instrumental"] is True
    assert body["output_format"] == "url"
    assert body["audio_setting"] == {"format": "mp3"}
    assert "guqin" in body["prompt"]
    assert "pr_tokenhub_test" not in body["prompt"]
    assert TEST_KEY not in json.dumps(body)

    meta = provider.last_run_metadata
    assert meta["provider"] == "tokenhub"
    assert meta["provider_label"] == "tokenhub/minimax-music-v3.0"
    assert meta["trace_id"] == "trace-tokenhub-1"
    assert meta["request_id"] == "req-tokenhub-1"
    assert meta["total_tokens"] == 1234
    assert meta["provider_reported_duration_ms"] == 25364
    assert meta["provider_reported_duration_seconds"] == pytest.approx(25.364)
    assert provider.health().status == "healthy"


def test_milliseconds_to_seconds_conversion():
    assert milliseconds_to_seconds(25364) == pytest.approx(25.364)
    assert milliseconds_to_seconds(60_000) == pytest.approx(60.0)
    assert milliseconds_to_seconds(0) == 0.0


# ------------------------------------------------------------------ url success


def test_url_response_is_downloaded_immediately_and_saved(tmp_path):
    audio = mp3_bytes(seconds=2)
    temp_url = "https://cdn.tokenhub-audio.example.com/tmp/audio-abc.mp3"
    poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
    downloader = FakeDownloader(payload=audio)
    provider = _provider(tmp_path, poster, downloader)
    task = provider.create_task(_request())

    assert task.status == "succeeded"
    assert downloader.calls == [temp_url]
    assert downloader.max_bytes_seen == [provider.max_download_bytes]
    assert provider.download_calls == 1
    stored = Path(task.asset_locator)
    assert stored.is_file() and stored.read_bytes() == audio
    # the temporary provider URL is never persisted in the task payload
    assert temp_url not in task.model_dump_json()
    assert "cdn.tokenhub-audio.example.com" not in task.model_dump_json()


# --------------------------------------------------------------- url security


def test_plain_http_audio_url_is_rejected_without_download(tmp_path):
    temp_url = "http://cdn.example.com/audio.mp3"
    poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
    downloader = FakeDownloader(payload=mp3_bytes())
    provider = _provider(tmp_path, poster, downloader)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert downloader.calls == []  # never fetched over plain HTTP


def test_internal_and_loopback_hosts_are_rejected(tmp_path):
    for bad_url in (
        "https://127.0.0.1/audio.mp3",
        "https://10.1.2.3/audio.mp3",
        "https://192.168.1.10/audio.mp3",
        "https://169.254.169.254/latest/meta-data/audio.mp3",
        "https://localhost/audio.mp3",
        "https://metadata.internal/audio.mp3",
    ):
        poster = FakePoster(response=FakeResponse(text=_completed_body(bad_url)))
        downloader = FakeDownloader(payload=mp3_bytes())
        provider = _provider(tmp_path, poster, downloader)
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request())
        assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED", bad_url
        assert downloader.calls == [], bad_url


def test_redirect_to_unsafe_final_url_is_rejected(tmp_path):
    temp_url = "https://cdn.example.com/audio.mp3"
    # provider link redirects to plain HTTP or an internal address
    for unsafe_final in ("http://cdn.example.com/audio.mp3", "https://127.0.0.1/audio.mp3"):
        poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
        downloader = FakeDownloader(payload=mp3_bytes(), final_url=unsafe_final)
        provider = _provider(tmp_path, poster, downloader)
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request())
        assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED", unsafe_final
        assert not list((tmp_path / "generated").glob("**/*")), unsafe_final


def test_public_https_redirect_is_allowed(tmp_path):
    audio = mp3_bytes(seconds=2)
    temp_url = "https://cdn.example.com/audio.mp3"
    final_url = "https://audio-cdn.tencentmaas.com/final/track.mp3"
    poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
    downloader = FakeDownloader(payload=audio, final_url=final_url)
    provider = _provider(tmp_path, poster, downloader)
    task = provider.create_task(_request())
    assert task.status == "succeeded"
    assert final_url not in task.model_dump_json()


def test_oversized_url_download_is_rejected(tmp_path):
    temp_url = "https://cdn.example.com/huge.mp3"
    poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
    downloader = FakeDownloader(error=AudioDownloadTooLarge("too big"))
    provider = _provider(tmp_path, poster, downloader, max_download_bytes=1024)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert not list((tmp_path / "generated").glob("**/*"))


def test_oversized_downloaded_payload_is_rejected(tmp_path):
    temp_url = "https://cdn.example.com/huge.mp3"
    poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
    downloader = FakeDownloader(payload=mp3_bytes(seconds=5))
    provider = _provider(tmp_path, poster, downloader, max_download_bytes=64)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"


def test_oversized_hex_payload_is_rejected(tmp_path):
    poster = FakePoster(response=FakeResponse(text=_completed_body(mp3_bytes(seconds=5).hex())))
    provider = _provider(tmp_path, poster, max_download_bytes=64)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"


# ------------------------------------------------------------- fail-closed rules


@pytest.mark.parametrize(
    ("status_code", "expected", "retryable"),
    [
        (401, "GENERATION_PROVIDER_AUTH_FAILED", False),
        (403, "GENERATION_PROVIDER_AUTH_FAILED", False),
        (400, "GENERATION_PROVIDER_REJECTED", False),
        (429, "GENERATION_PROVIDER_RATE_LIMITED", True),
        (500, "GENERATION_PROVIDER_UNAVAILABLE", True),
        (503, "GENERATION_PROVIDER_UNAVAILABLE", True),
    ],
)
def test_http_status_mapping(tmp_path, status_code, expected, retryable):
    poster = FakePoster(
        response=FakeResponse(status_code=status_code, text=json.dumps({"message": "x"}))
    )
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == expected
    assert caught.value.retryable is retryable
    assert len(poster.calls) == 1


@pytest.mark.parametrize(
    ("base_status", "expected"),
    [
        (1002, "GENERATION_PROVIDER_RATE_LIMITED"),
        (1004, "GENERATION_PROVIDER_AUTH_FAILED"),
        (2049, "GENERATION_PROVIDER_AUTH_FAILED"),
        (1008, "GENERATION_PROVIDER_REJECTED"),
        (1026, "GENERATION_PROVIDER_REJECTED"),
        (2013, "GENERATION_PROVIDER_REJECTED"),
    ],
)
def test_base_resp_status_code_mapping(tmp_path, base_status, expected):
    poster = FakePoster(
        response=FakeResponse(text=_completed_body(mp3_bytes().hex(), base_status=base_status))
    )
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == expected
    assert len(poster.calls) == 1


def test_in_progress_status_fails_closed(tmp_path):
    body = json.dumps(
        {"data": {"status": 1, "audio": None}, "base_resp": {"status_code": 0}}
    )
    poster = FakePoster(response=FakeResponse(text=body))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert not list((tmp_path / "generated").glob("**/*"))
    assert len(poster.calls) == 1


def test_empty_and_garbage_audio_fail_explicitly(tmp_path):
    for audio_ref in ("", "  ", "not-hex-and-not-url"):
        poster = FakePoster(response=FakeResponse(text=_completed_body(audio_ref)))
        provider = _provider(tmp_path, poster)
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request())
        assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
        assert len(poster.calls) == 1


def test_non_audio_hex_fails_explicitly(tmp_path):
    poster = FakePoster(response=FakeResponse(text=_completed_body(b"plain text".hex())))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"


def test_invalid_json_response_fails_explicitly(tmp_path):
    poster = FakePoster(response=FakeResponse(text="<html>not json</html>"))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert len(poster.calls) == 1


def test_transport_failures_are_explicit_and_never_retried(tmp_path):
    timeout_provider = _provider(tmp_path, FakePoster(error=requests.Timeout("slow")))
    with pytest.raises(MusicProviderFailureV3) as caught:
        timeout_provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_TIMEOUT"
    assert timeout_provider.post_calls == 1

    conn_provider = _provider(tmp_path, FakePoster(error=requests.ConnectionError("down")))
    with pytest.raises(MusicProviderFailureV3) as caught:
        conn_provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert conn_provider.post_calls == 1


def test_url_download_failure_is_explicit_and_not_retried(tmp_path):
    temp_url = "https://cdn.example.com/tmp/audio-abc.mp3"
    poster = FakePoster(response=FakeResponse(text=_completed_body(temp_url)))
    downloader = FakeDownloader(error=requests.Timeout("download slow"))
    provider = _provider(tmp_path, poster, downloader)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_TIMEOUT"
    assert provider.post_calls == 1
    assert len(downloader.calls) == 1


def test_secret_never_leaks_into_metadata_or_errors(tmp_path):
    poster = FakePoster(
        response=FakeResponse(
            status_code=401,
            text=json.dumps({"base_resp": {"status_code": 1004, "status_msg": f"bad {TEST_KEY}"}}),
        )
    )
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert TEST_KEY not in str(caught.value)
    assert TEST_KEY not in json.dumps(provider.last_run_metadata)
    assert TEST_KEY not in provider.health().model_dump_json()


# --------------------------------------------------------------------- protocol


def test_get_and_cancel_report_unsupported_surfaces(tmp_path):
    provider = _provider(tmp_path, FakePoster())
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.get_task("trace-1")
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.cancel_task("trace-1")
    assert caught.value.error_code == "GENERATION_CANCEL_UNSUPPORTED"


def test_async_create_matches_sync(tmp_path):
    audio = mp3_bytes(seconds=2)
    provider = _provider(
        tmp_path, FakePoster(response=FakeResponse(text=_completed_body(audio.hex())))
    )
    sync_task = provider.create_task(_request())
    async_task = asyncio.run(provider.acreate_task(_request()))
    assert async_task.status == "succeeded"
    assert async_task.asset_locator == sync_task.asset_locator
    assert Path(async_task.asset_locator).read_bytes() == audio


# --------------------------------------------- rule-asset compatibility (music rules)

CHINESE_INSTRUMENT_CASES = [
    ("古琴", "guqin"),
    ("箫", "xiao"),
    ("琵琶", "pipa"),
    ("笛", "dizi"),
    ("埙", "xun"),
]


@pytest.mark.parametrize(("chinese", "token"), CHINESE_INSTRUMENT_CASES)
def test_chinese_rule_instrument_normalizes_for_the_provider(tmp_path, chinese, token):
    assert normalize_instrument(chinese) == token
    assert normalize_instruments([chinese]) == [token]
    assert token in SUPPORTED_INSTRUMENTS

    audio = mp3_bytes(seconds=2)
    poster = FakePoster(response=FakeResponse(text=_completed_body(audio.hex())))
    provider = _provider(tmp_path, poster)
    task = provider.create_task(_request(instruments=[chinese]))

    assert task.status == "succeeded"
    assert len(poster.calls) == 1  # single POST, automatic retry 0
    prompt = poster.calls[0]["json"]["prompt"]
    assert token in prompt
    assert chinese not in prompt  # provider prompt uses normalized tokens only
    # the request object itself is untouched (display values preserved upstream)
    assert _request(instruments=[chinese]).generation_spec.instruments == [chinese]


def test_instrument_alias_table_is_fixed_and_bidirectional():
    for chinese, token in CHINESE_INSTRUMENT_CASES:
        assert INSTRUMENT_ALIASES[chinese] == token
        assert INSTRUMENT_ALIASES[token] == token
    assert len(SUPPORTED_INSTRUMENTS) == 5


def test_unknown_instrument_fails_explicitly_before_any_post(tmp_path):
    for unknown in ("唢呐", "suona", "古筝", "guzheng", "erhu", "unknown"):
        poster = FakePoster(response=FakeResponse(text=_completed_body(mp3_bytes().hex())))
        provider = _provider(tmp_path, poster)
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request(instruments=[unknown]))
        assert caught.value.error_code == "GENERATION_INSTRUMENT_UNSUPPORTED", unknown
        assert poster.calls == [], unknown
        assert not list((tmp_path / "generated").glob("**/*")), unknown


def test_mixed_known_and_unknown_instrument_fails_explicitly(tmp_path):
    poster = FakePoster(response=FakeResponse(text=_completed_body(mp3_bytes().hex())))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request(instruments=["古琴", "唢呐"]))
    assert caught.value.error_code == "GENERATION_INSTRUMENT_UNSUPPORTED"
    assert poster.calls == []


def test_no_extra_ambient_never_renders_a_contradictory_prompt(tmp_path):
    poster = FakePoster(response=FakeResponse(text=_completed_body(mp3_bytes().hex())))
    provider = _provider(tmp_path, poster)
    provider.create_task(_request(instruments=["古琴"], ambient=["无额外环境音"]))
    prompt = poster.calls[0]["json"]["prompt"]
    assert "无额外环境音" not in prompt
    assert "ambience" not in prompt
    assert "Atmosphere" not in prompt


def test_real_ambient_still_renders_while_no_ambient_token_is_dropped(tmp_path):
    poster = FakePoster(response=FakeResponse(text=_completed_body(mp3_bytes().hex())))
    provider = _provider(tmp_path, poster)
    provider.create_task(
        _request(instruments=["箫"], ambient=["无额外环境音", "water"])
    )
    prompt = poster.calls[0]["json"]["prompt"]
    assert "soft water ambience" in prompt
    assert "无额外环境音" not in prompt


def test_duration_is_a_prompt_target_not_a_provider_field(tmp_path):
    audio = mp3_bytes(seconds=3)
    poster = FakePoster(response=FakeResponse(text=_completed_body(audio.hex())))
    provider = _provider(tmp_path, poster)
    task = provider.create_task(_request(duration_seconds=60))

    assert task.status == "succeeded"
    body = poster.calls[0]["json"]
    # TokenHub music has no duration parameter at all
    for forbidden_key in ("duration", "seconds_total", "length", "duration_seconds"):
        assert forbidden_key not in body
    prompt = body["prompt"]
    assert "target length about 60 seconds" in prompt

    meta = provider.last_run_metadata
    # provider-reported actual duration (ms -> s) stays separate from the target
    assert meta["provider_reported_duration_ms"] == 25364
    assert meta["provider_reported_duration_seconds"] == pytest.approx(25.364)
    assert meta["provider_reported_duration_seconds"] != 60


def test_project_internal_duration_cap_is_not_a_provider_claim():
    provider = _provider(Path("."), FakePoster())
    assert (
        provider.capabilities().max_duration_seconds
        == PROJECT_INTERNAL_MAX_DURATION_SECONDS
    )
    assert TOKENHUB_MAX_DURATION_SECONDS == PROJECT_INTERNAL_MAX_DURATION_SECONDS
    docstring = tokenhub_module.__doc__ or ""
    assert "NO duration parameter" in docstring
    assert "TARGET only" in docstring


@pytest.mark.parametrize(
    "failure_payload",
    ["http_500", "base_resp_1008", "empty_audio", "in_progress"],
)
def test_real_failure_never_returns_success_and_never_switches_to_mock(tmp_path, failure_payload):
    if failure_payload == "http_500":
        poster = FakePoster(response=FakeResponse(status_code=500, text='{"message":"x"}'))
    elif failure_payload == "base_resp_1008":
        poster = FakePoster(response=FakeResponse(text=_completed_body("", base_status=1008)))
    elif failure_payload == "empty_audio":
        poster = FakePoster(response=FakeResponse(text=_completed_body("")))
    else:
        poster = FakePoster(
            response=FakeResponse(
                text=json.dumps({"data": {"status": 1, "audio": None}, "base_resp": {"status_code": 0}})
            )
        )
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request(instruments=["古琴"], ambient=["无额外环境音"]))
    assert caught.value.error_code in {
        "GENERATION_PROVIDER_UNAVAILABLE",
        "GENERATION_PROVIDER_REJECTED",
    }
    assert len(poster.calls) == 1  # single POST, automatic retry 0
    assert not list((tmp_path / "generated").glob("**/*"))
    # no hidden success / fallback object is produced by the provider itself
    assert provider.last_run_metadata.get("error_code") is not None

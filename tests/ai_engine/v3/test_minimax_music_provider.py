"""MiniMax Music provider adapter — honest mapping, fail-closed behavior.

Covers:
  * bundle wiring: MUSIC_PROVIDER=minimax complete -> real adapter; any
    incomplete/invalid config -> NotConfigured (readiness), never Mock.
  * capabilities honesty: no fabricated progress/cancel support.
  * real success: hex audio decoded, format-sniffed and materialized into the
    owned media root; provider_task_id opaque; no secret/URL leakage.
  * real failure mapping: MiniMax base_resp codes, HTTP errors, timeouts,
    in-progress status without a poll handle, empty/garbage audio.
  * sync and async protocol surfaces.
"""

import asyncio
import json
from pathlib import Path

import pytest

from backend.ai_engine.v3.generation_provider_adapter import (
    NotConfiguredMusicProvider,
    build_music_provider_bundle,
)
from backend.ai_engine.v3.minimax_music_provider import (
    DEFAULT_MINIMAX_BASE_URL,
    MAX_DURATION_SECONDS,
    MiniMaxMusicProvider,
    REFERENCE_INSTRUMENTS,
)
from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.app.schemas.v3.music import (
    MusicProviderCapabilities,
    ProviderMusicRequest,
    ProviderTask,
)


def _tone_profile(source_type: str = "available") -> dict[str, object]:
    return {
        "schema_version": "tone_profile_v3.0",
        "status": source_type,
        "weights": {
            "jiao": 0.2,
            "zhi": 0.2,
            "gong": 0.2,
            "shang": 0.2,
            "yu": 0.2,
        },
        "dominant_tone": "gong",
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {"diagnosis_id": "diag_test", "supporting_fact_ids": ["fev_test"]},
    }


def _generation_spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 300,
        "instruments": ["guqin", "xiao"],
        "ambient_sounds": ["water"],
        "structure": {"intro_seconds": 30, "main_seconds": 240, "outro_seconds": 30},
        "energy_curve": "gentle_decline",
        "forbidden_constraints": ["sharp_high_frequency"],
        "fallback_policy": {"allow_local_matching": True},
    }


def _request(output_format: str = "mp3") -> ProviderMusicRequest:
    return ProviderMusicRequest(
        provider_request_id="pr_minimax_test",
        generation_spec=_generation_spec(),
        output_format=output_format,  # type: ignore[arg-type]
        callback_ref=None,
    )


def _minimax_env(*, api_key: str = "sk-test-minimax-secret", **overrides) -> dict[str, str]:
    env = {
        "MUSIC_PROVIDER": "minimax",
        "MUSIC_PROVIDER_BASE_URL": "https://minimax.example.invalid",
        "MUSIC_PROVIDER_API_KEY": api_key,
        "MUSIC_PROVIDER_MODEL": "music-3.0",
        "HARMONY_MEDIA_ROOT": str(Path("unused")),
    }
    env.update(overrides)
    return env


def _completed_body(audio: bytes, *, status_code: int = 0) -> bytes:
    return json.dumps(
        {
            "data": {"status": 2, "audio": audio.hex()},
            "trace_id": "trace-123-abc",
            "extra_info": {"music_duration": 300000},
            "base_resp": {"status_code": status_code, "status_msg": "success"},
        }
    ).encode("utf-8")


def _mp3_bytes() -> bytes:
    return b"\xff\xfb\x90\x64\x00\x00\x00\x00\x00\x00"


class FakeTransport:
    def __init__(self, response: bytes | None = None, error: BaseException | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body})
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake transport has no response")
        return self.response


def _provider(tmp_path: Path, transport) -> MiniMaxMusicProvider:
    return MiniMaxMusicProvider(
        base_url="https://minimax.example.invalid",
        api_key="sk-test-minimax-secret",
        model="music-3.0",
        media_root=tmp_path,
        transport=transport,
    )


# ---------------------------------------------------------------- bundle wiring


def test_minimax_env_builds_real_adapter(tmp_path):
    env = _minimax_env(HARMONY_MEDIA_ROOT=str(tmp_path))
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, MiniMaxMusicProvider)
    assert bundle.provider.provider_name == "minimax"
    assert bundle.provider.model == "music-3.0"
    assert bundle.health.status == "configured"
    assert bundle.health.provider == "minimax"
    serialized = bundle.health.model_dump_json()
    assert "sk-test-minimax-secret" not in serialized
    assert "minimax.example.invalid" not in serialized


def test_minimax_env_missing_key_keeps_readiness_not_configured(tmp_path):
    env = _minimax_env(api_key="")
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.provider.provider_name == "minimax"
    assert bundle.health.status == "not_configured"
    with pytest.raises(MusicProviderFailureV3) as caught:
        bundle.provider.create_task(_request())
    assert caught.value.error_code == "PROVIDER_NOT_CONFIGURED"


def test_minimax_env_invalid_model_keeps_readiness_not_configured(tmp_path):
    env = _minimax_env()
    env["MUSIC_PROVIDER_MODEL"] = "not-a-minimax-model"
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"


def test_unknown_provider_name_still_not_configured(tmp_path):
    env = _minimax_env()
    env["MUSIC_PROVIDER"] = "sunokun"
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"


def test_empty_env_still_not_configured():
    bundle = build_music_provider_bundle({})
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"


# ------------------------------------------------------------- capability gates


def test_capabilities_are_honest():
    provider = _provider(Path("."), FakeTransport(response=_completed_body(b"x")))
    caps: MusicProviderCapabilities = provider.capabilities()
    # MiniMax Music documents no progress/cancel surface; never pretend.
    assert caps.supports_progress is False
    assert caps.supports_cancel is False
    assert caps.max_duration_seconds == MAX_DURATION_SECONDS
    assert "mp3" in caps.supported_formats and "wav" in caps.supported_formats
    assert set(REFERENCE_INSTRUMENTS).issubset(caps.supported_instruments)


# ------------------------------------------------------------ real success path


def test_create_task_materializes_generated_audio(tmp_path):
    audio = _mp3_bytes()
    transport = FakeTransport(response=_completed_body(audio))
    provider = _provider(tmp_path, transport)
    task = provider.create_task(_request())

    assert isinstance(task, ProviderTask)
    assert task.status == "succeeded"
    assert task.progress_value == 100
    assert task.error_code is None
    assert task.asset_locator is not None
    stored = Path(task.asset_locator)
    assert stored.is_file()
    assert stored.read_bytes() == audio
    assert str(tmp_path) in task.asset_locator
    # private base URL / key must never reach the task payload
    assert "minimax.example.invalid" not in task.model_dump_json()
    assert "sk-test-minimax-secret" not in task.model_dump_json()
    # exactly one POST to the official path
    assert len(transport.calls) == 1
    assert transport.calls[0]["url"] == "https://minimax.example.invalid/v1/music_generation"
    sent_headers = transport.calls[0]["headers"]
    assert sent_headers["Authorization"] == "Bearer sk-test-minimax-secret"
    body = json.loads(transport.calls[0]["body"])
    assert body["model"] == "music-3.0"
    assert body["is_instrumental"] is True
    assert body["output_format"] == "hex"
    assert body["audio_setting"]["format"] == "mp3"
    # prompt carries spec parameters, never the request id
    assert "guqin" in body["prompt"] and "xiao" in body["prompt"]
    assert "bpm 60" in body["prompt"]
    assert "pr_minimax_test" not in body["prompt"]
    assert len(body["prompt"]) <= 2000
    assert provider.health().status == "healthy"
    assert provider.last_run_metadata["provider"] == "minimax"
    assert provider.last_run_metadata["error_code"] is None


def test_async_create_task_matches_sync_result(tmp_path):
    audio = _mp3_bytes()
    provider = _provider(tmp_path, FakeTransport(response=_completed_body(audio)))
    sync_result = provider.create_task(_request())
    async_result = asyncio.run(provider.acreate_task(_request()))
    assert async_result.status == "succeeded"
    assert Path(async_result.asset_locator).read_bytes() == audio
    assert async_result.asset_locator == sync_result.asset_locator


# ------------------------------------------------------------- fail-closed rules


def test_in_progress_without_poll_handle_fails_closed(tmp_path):
    body = json.dumps(
        {
            "data": {"status": 1, "audio": None},
            "trace_id": "trace-abc",
            "base_resp": {"status_code": 0, "status_msg": "processing"},
        }
    ).encode("utf-8")
    provider = _provider(tmp_path, FakeTransport(response=body))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert caught.value.retryable is True
    # no fake success file may be produced
    assert list((tmp_path / "generated").glob("**/*")) == []


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (1004, "GENERATION_PROVIDER_AUTH_FAILED"),
        (2049, "GENERATION_PROVIDER_AUTH_FAILED"),
        (1002, "GENERATION_PROVIDER_RATE_LIMITED"),
        (1008, "GENERATION_PROVIDER_REJECTED"),
        (1026, "GENERATION_PROVIDER_REJECTED"),
        (2013, "GENERATION_PROVIDER_REJECTED"),
    ],
)
def test_minimax_base_resp_errors_map_to_stable_codes(tmp_path, status_code, expected):
    body = json.dumps(
        {
            "data": {"status": 2, "audio": None},
            "base_resp": {"status_code": status_code, "status_msg": "vendor detail"},
        }
    ).encode("utf-8")
    provider = _provider(tmp_path, FakeTransport(response=body))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == expected
    # vendor raw text never leaks into the safe failure
    assert "vendor detail" not in caught.value.safe_message


def test_empty_audio_payload_fails_explicitly(tmp_path):
    audio = b""
    provider = _provider(tmp_path, FakeTransport(response=_completed_body(audio)))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert caught.value.retryable is False


def test_non_audio_garbage_fails_explicitly(tmp_path):
    audio = b"\x00\x01\x02\x03 not-audio at all"
    provider = _provider(tmp_path, FakeTransport(response=_completed_body(audio)))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"


def test_invalid_json_response_fails_explicitly(tmp_path):
    provider = _provider(tmp_path, FakeTransport(response=b"<html>not json"))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"


# ------------------------------------------------------------- HTTP/timeout map


def test_http_auth_errors_map_to_auth_failed(tmp_path):
    from urllib.error import HTTPError

    error = HTTPError("https://x", 401, "unauthorized", None, None)
    provider = _provider(tmp_path, FakeTransport(error=error))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_AUTH_FAILED"
    assert caught.value.retryable is False


def test_http_429_maps_to_rate_limited(tmp_path):
    from urllib.error import HTTPError

    provider = _provider(
        tmp_path, FakeTransport(error=HTTPError("https://x", 429, "slow down", None, None))
    )
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_RATE_LIMITED"
    assert caught.value.retryable is True


def test_http_500_maps_to_unavailable(tmp_path):
    from urllib.error import HTTPError

    provider = _provider(
        tmp_path, FakeTransport(error=HTTPError("https://x", 503, "boom", None, None))
    )
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert caught.value.retryable is True


def test_timeout_maps_to_timeout(tmp_path):
    from backend.ai_engine.providers import ReadTimeoutError

    provider = _provider(tmp_path, FakeTransport(error=ReadTimeoutError()))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_TIMEOUT"
    assert caught.value.retryable is True


# ------------------------------------------------------------------- protocol


def test_get_task_refuses_invented_polling(tmp_path):
    provider = _provider(tmp_path, FakeTransport(response=b""))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.get_task("trace-1")
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert caught.value.retryable is True


def test_cancel_task_reports_unsupported_capability(tmp_path):
    provider = _provider(tmp_path, FakeTransport(response=b""))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.cancel_task("trace-1")
    assert caught.value.error_code == "GENERATION_CANCEL_UNSUPPORTED"
    assert caught.value.retryable is False


def test_duration_beyond_capability_is_rejected_before_call(tmp_path):
    request = _request().model_copy(deep=True)
    spec = request.generation_spec.model_copy(update={"duration_seconds": 900})
    request = request.model_copy(update={"generation_spec": spec})
    provider = _provider(tmp_path, FakeTransport(response=_completed_body(_mp3_bytes())))
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(request)
    assert caught.value.error_code == "GENERATION_DURATION_UNSUPPORTED"

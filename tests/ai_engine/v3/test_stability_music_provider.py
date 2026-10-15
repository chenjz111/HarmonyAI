"""Stability AI Stable Audio 2.5 adapter — real mode, fail-closed.

Covers:
  * bundle wiring: MUSIC_PROVIDER=stability + STABILITY_API_KEY -> real
    adapter; missing key/invalid model -> NotConfigured (readiness), never Mock.
  * official multipart request via requests-style poster (no hand-written
    boundary), Authorization: Bearer <STABILITY_API_KEY>.
  * exactly one POST per generation (automatic retry = 0) on success and
    failure paths (no duplicate paid generation).
  * audio/mpeg binary is validated and materialized into the owned media root.
  * capability honesty and HTTP/error mapping; no secret leakage.
"""

import asyncio
import json
from pathlib import Path
import re

import pytest
import requests

from backend.ai_engine.v3.prompt_compiler import (
    PROMPT_COMPILER_VERSION,
    PROMPT_MAX_LENGTH,
    TONE_PROMPT_DESCRIPTORS,
    PromptDialect,
    compile_music_prompt,
)

from backend.ai_engine.v3.generation_provider_adapter import (
    NotConfiguredMusicProvider,
    build_music_provider_bundle,
)
from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.ai_engine.v3.stability_music_provider import (
    DEFAULT_STABILITY_MODEL,
    STABILITY_AUDIO_PATH,
    STABILITY_MAX_DURATION_SECONDS,
    STABILITY_PROMPT_MAX_LENGTH,
    StabilityMusicProvider,
    _requests_poster,
)
from backend.app.schemas.v3.music import (
    MusicProviderCapabilities,
    ProviderMusicRequest,
    ProviderTask,
)

# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #


def _tone_profile(source_type: str = "available") -> dict[str, object]:
    del source_type  # V3.1 ToneProfile has no status variant
    return {
        "schema_version": "tone_profile_v3.2",
        "regulation_mode": "personalized_five_tone",
        "weights": {
            "jiao": 0.2,
            "zhi": 0.2,
            "gong": 0.2,
            "shang": 0.2,
            "yu": 0.2,
        },
        "primary_tone": "gong",
        "secondary_tone": None,
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {
            "diagnosis_id": "diag_test",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": ["fev_test"],
        },
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


def _request() -> ProviderMusicRequest:
    return ProviderMusicRequest(
        provider_request_id="pr_stability_test",
        generation_spec=_generation_spec(),
        output_format="mp3",
        callback_ref=None,
    )


def mp3_bytes(*, seconds: float = 3.0) -> bytes:
    """Synthetic MPEG1 Layer III 128 kbps 44.1 kHz stream of ~seconds length."""
    bitrate_kbps = 128
    samplerate = 44100
    samples_per_frame = 1152
    frame_length = int(samples_per_frame * bitrate_kbps * 1000 / (8 * samplerate))
    header = b"\xff\xfb\x90\x00"  # MPEG1, Layer III, no CRC, 128kbps, 44.1kHz
    frame = header + bytes(max(0, frame_length - 4))
    frames = max(1, int(seconds * samplerate / samples_per_frame) + 1)
    return frame * frames


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"",
        content_type: str = "audio/mpeg",
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}
        self.text = text


class FakePoster:
    def __init__(self, response: FakeResponse | None = None, error: BaseException | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, url, *, headers, data, files, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "data": dict(data),
                "files": files,
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake poster has no response")
        return self.response


def _provider(tmp_path: Path, poster: FakePoster) -> StabilityMusicProvider:
    return StabilityMusicProvider(
        api_key="sk-test-stability-secret",
        model=DEFAULT_STABILITY_MODEL,
        base_url="https://stability.example.invalid",
        media_root=tmp_path,
        poster=poster,
    )


def _stability_env(**overrides) -> dict[str, str]:
    env = {
        "MUSIC_PROVIDER": "stability",
        "MUSIC_PROVIDER_MODEL": DEFAULT_STABILITY_MODEL,
        "MUSIC_PROVIDER_BASE_URL": "https://stability.example.invalid",
        "STABILITY_API_KEY": "sk-test-stability-secret",
        "HARMONY_MEDIA_ROOT": str(Path("unused")),
    }
    env.update(overrides)
    return env


# ---------------------------------------------------------------- bundle wiring


def test_stability_env_is_historical_and_not_wired(tmp_path):
    # Stability is no longer the Sprint 5 official provider (Tencent Cloud
    # TokenHub / MiniMax is). The adapter stays in the tree as history only.
    bundle = build_music_provider_bundle(_stability_env(HARMONY_MEDIA_ROOT=str(tmp_path)))
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.provider.provider_name == "stability"
    assert bundle.health.status == "not_configured"
    assert bundle.health.safe_message is not None
    assert "历史" in bundle.health.safe_message
    serialized = bundle.health.model_dump_json()
    assert "sk-test-stability-secret" not in serialized
    assert "stability.example.invalid" not in serialized
    # the Stability adapter itself remains importable as an un-enabled reference
    assert StabilityMusicProvider is not None


def test_stability_env_missing_key_keeps_readiness_not_configured(tmp_path):
    bundle = build_music_provider_bundle(
        _stability_env(STABILITY_API_KEY="", HARMONY_MEDIA_ROOT=str(tmp_path))
    )
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.provider.provider_name == "stability"
    assert bundle.health.status == "not_configured"
    with pytest.raises(MusicProviderFailureV3) as caught:
        bundle.provider.create_task(_request())
    assert caught.value.error_code == "PROVIDER_NOT_CONFIGURED"


def test_stability_env_invalid_model_keeps_readiness_not_configured(tmp_path):
    env = _stability_env(HARMONY_MEDIA_ROOT=str(tmp_path))
    env["MUSIC_PROVIDER_MODEL"] = "stable-audio-3.0"
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"


def test_stability_env_wrong_key_var_keeps_readiness_not_configured(tmp_path):
    # Only STABILITY_API_KEY is honored; MUSIC_PROVIDER_API_KEY must not leak
    # through as a substitute.
    env = _stability_env(STABILITY_API_KEY="", HARMONY_MEDIA_ROOT=str(tmp_path))
    env["MUSIC_PROVIDER_API_KEY"] = "sk-other-secret"
    bundle = build_music_provider_bundle(env)
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"


# ------------------------------------------------------------- capability gates


def test_capabilities_are_honest():
    provider = _provider(Path("."), FakePoster())
    caps: MusicProviderCapabilities = provider.capabilities()
    assert caps.supports_progress is False
    assert caps.supports_cancel is False
    assert caps.max_duration_seconds == STABILITY_MAX_DURATION_SECONDS
    assert caps.supported_formats == ["mp3"]
    assert "guqin" in caps.supported_instruments


def test_duration_beyond_capability_is_rejected_before_any_call(tmp_path):
    request = _request().model_copy(deep=True)
    spec = request.generation_spec.model_copy(update={"duration_seconds": 300})
    request = request.model_copy(update={"generation_spec": spec})
    poster = FakePoster(response=FakeResponse(content=mp3_bytes()))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(request)
    assert caught.value.error_code == "GENERATION_DURATION_UNSUPPORTED"
    assert poster.calls == []


# ------------------------------------------------------------ real success path


def test_create_task_posts_exactly_once_and_materializes_mp3(tmp_path):
    audio = mp3_bytes(seconds=3)
    poster = FakePoster(response=FakeResponse(content=audio))
    provider = _provider(tmp_path, poster)
    task = provider.create_task(_request())

    assert isinstance(task, ProviderTask)
    assert task.status == "succeeded"
    assert task.progress_value == 100
    assert task.error_code is None
    assert task.provider_task_id.startswith("stability-")
    stored = Path(task.asset_locator)
    assert stored.is_file()
    assert stored.read_bytes() == audio
    assert "stability.example.invalid" not in task.model_dump_json()
    assert "sk-test-stability-secret" not in task.model_dump_json()

    assert len(poster.calls) == 1  # automatic retry is 0
    call = poster.calls[0]
    assert call["url"] == "https://stability.example.invalid" + STABILITY_AUDIO_PATH
    headers = call["headers"]
    assert headers["Authorization"] == "Bearer sk-test-stability-secret"
    # multipart is produced by the client; the boundary is never hand-written
    assert "content-type" not in headers
    data = call["data"]
    # field names follow the Owner-verified successful request / official schema
    assert data["model"] == DEFAULT_STABILITY_MODEL
    assert data["duration"] == 60
    assert data["steps"] == 8
    assert data["cfg_scale"] == 1.0
    assert "guqin" in data["prompt"]
    assert "pr_stability_test" not in data["prompt"]
    assert "sk-test-stability-secret" not in str(call["data"])
    assert call["files"]  # a non-empty files part forces multipart/form-data
    assert provider.health().status == "healthy"
    assert provider.last_run_metadata["provider"] == "stability"
    assert provider.last_run_metadata["error_code"] is None


def test_async_create_task_matches_sync_result(tmp_path):
    audio = mp3_bytes(seconds=2)
    provider = _provider(tmp_path, FakePoster(response=FakeResponse(content=audio)))
    sync_result = provider.create_task(_request())
    async_result = asyncio.run(provider.acreate_task(_request()))
    assert async_result.status == "succeeded"
    assert Path(async_result.asset_locator).read_bytes() == audio
    assert async_result.asset_locator == sync_result.asset_locator


# ------------------------------------------------------------- fail-closed rules


def test_http_status_mapping(tmp_path):
    cases = [
        (401, "GENERATION_PROVIDER_AUTH_FAILED", False),
        (403, "GENERATION_PROVIDER_AUTH_FAILED", False),
        (402, "GENERATION_PROVIDER_REJECTED", False),
        (400, "GENERATION_PROVIDER_REJECTED", False),
        (422, "GENERATION_PROVIDER_REJECTED", False),
        (429, "GENERATION_PROVIDER_RATE_LIMITED", True),
        (500, "GENERATION_PROVIDER_UNAVAILABLE", True),
        (503, "GENERATION_PROVIDER_UNAVAILABLE", True),
    ]
    for status, expected, retryable in cases:
        poster = FakePoster(
            response=FakeResponse(
                status_code=status,
                content=b"",
                content_type="application/json",
                text=json.dumps({"name": "some_error", "message": "detail"}),
            )
        )
        provider = _provider(tmp_path, poster)
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request())
        assert caught.value.error_code == expected, status
        assert caught.value.retryable is retryable, status
        # no automatic retry on the failure path either
        assert len(poster.calls) == 1


def test_error_json_is_never_leaked_as_credential(tmp_path):
    poster = FakePoster(
        response=FakeResponse(
            status_code=401,
            content=b"",
            content_type="application/json",
            text=json.dumps(
                {"name": "unauthorized", "message": "bad key sk-test-stability-secret"}
            ),
        )
    )
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_AUTH_FAILED"
    # raw vendor message with the key value never enters the safe message
    assert "sk-test-stability-secret" not in str(caught.value)
    assert "sk-test-stability-secret" not in repr(provider.last_run_metadata)


def test_wrong_content_type_fails_explicitly(tmp_path):
    poster = FakePoster(
        response=FakeResponse(
            status_code=200,
            content=b"not audio",
            content_type="application/json",
            text='{"name":"unexpected","message":"..."}',
        )
    )
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert not list((tmp_path / "generated").glob("**/*"))


def test_empty_or_garbage_audio_fails_explicitly(tmp_path):
    for payload in (b"", b"\x00\x01 not an mp3 at all"):
        poster = FakePoster(
            response=FakeResponse(status_code=200, content=payload, content_type="audio/mpeg")
        )
        provider = _provider(tmp_path, poster)
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request())
        assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
        assert len(poster.calls) == 1


def test_timeout_and_connection_failures_are_explicit(tmp_path):
    provider_timeout = _provider(
        tmp_path, FakePoster(error=requests.Timeout("too slow"))
    )
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider_timeout.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_TIMEOUT"
    assert caught.value.retryable is True
    assert provider_timeout.post_calls == 1  # no automatic retry

    provider_conn = _provider(
        tmp_path, FakePoster(error=requests.ConnectionError("boom"))
    )
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider_conn.create_task(_request())
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert caught.value.retryable is True
    assert provider_conn.post_calls == 1


# ------------------------------------------------------------------- protocol


def test_get_task_refuses_invented_polling(tmp_path):
    provider = _provider(tmp_path, FakePoster())
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.get_task("stability-abc")
    assert caught.value.error_code == "GENERATION_PROVIDER_UNAVAILABLE"


def test_cancel_task_reports_unsupported_capability(tmp_path):
    provider = _provider(tmp_path, FakePoster())
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.cancel_task("stability-abc")
    assert caught.value.error_code == "GENERATION_CANCEL_UNSUPPORTED"
    assert caught.value.retryable is False


def test_requests_poster_importable():
    assert callable(_requests_poster)


# --------------------------------------------------------------------------- #
# Sprint 6 Phase 5 — Prompt Compiler V2 integration (§15)
# --------------------------------------------------------------------------- #
TONE_CODES = ("jiao", "zhi", "gong", "shang", "yu")


def _request_with(*, instruments=None, ambient=None, constraints=None):
    spec = dict(_generation_spec())
    if instruments is not None:
        spec["instruments"] = instruments
    if ambient is not None:
        spec["ambient_sounds"] = ambient
    if constraints is not None:
        spec["forbidden_constraints"] = constraints
    return ProviderMusicRequest(
        provider_request_id="pr_stability_test",
        generation_spec=spec,  # type: ignore[arg-type]
        output_format="mp3",
        callback_ref=None,
    )


def test_stability_prompt_actually_uses_prompt_compiler_v2(tmp_path):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    request = _request_with(instruments=["古琴", "箫"])
    provider.create_task(request)

    prompt = poster.calls[0]["data"]["prompt"]
    expected = compile_music_prompt(request.generation_spec, PromptDialect.STABILITY)
    assert prompt == expected.text
    assert TONE_PROMPT_DESCRIPTORS["gong"] in prompt
    assert "primary tone emphasis 0.2" in prompt
    assert "Instruments: guqin, xiao" in prompt
    assert "古琴" not in prompt
    assert "total duration 60 seconds" in prompt


def test_stability_prompt_has_no_raw_tone_enum_leakage(tmp_path):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    provider.create_task(_request())
    prompt = poster.calls[0]["data"]["prompt"]
    for tone in TONE_CODES:
        assert not re.search(rf"\b{tone}\b", prompt, re.IGNORECASE), prompt


def test_stability_no_extra_ambient_never_renders_contradictory_text(tmp_path):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    provider.create_task(_request_with(ambient=["无额外环境音"]))
    prompt = poster.calls[0]["data"]["prompt"]
    assert "无额外环境音" not in prompt
    assert "Atmosphere" not in prompt
    assert "ambience" not in prompt


def test_stability_real_ambience_renders_and_mixed_input_is_not_contradictory(
    tmp_path,
):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    provider.create_task(_request_with(ambient=["water"]))
    assert "Atmosphere: soft water ambience." in poster.calls[0]["data"]["prompt"]

    provider.create_task(_request_with(ambient=["无额外环境音", "water"]))
    prompt = poster.calls[1]["data"]["prompt"]
    assert "Atmosphere: soft water ambience." in prompt
    assert "无额外环境音" not in prompt
    assert "soft 无额外环境音 ambience" not in prompt


def test_stability_unknown_instrument_fails_before_any_post(tmp_path):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    for instruments in (["suona"], ["古琴", "唢呐"]):
        with pytest.raises(MusicProviderFailureV3) as caught:
            provider.create_task(_request_with(instruments=instruments))
        assert caught.value.error_code == "GENERATION_INSTRUMENT_UNSUPPORTED"
    assert poster.calls == []
    assert provider.post_calls == 0


def test_stability_prompt_identity_is_recorded(tmp_path):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    provider.create_task(_request())
    prompt = poster.calls[0]["data"]["prompt"]
    metadata = provider.last_run_metadata
    assert metadata["compiler_version"] == PROMPT_COMPILER_VERSION
    assert metadata["dialect_id"] == PromptDialect.STABILITY.value
    assert metadata["prompt_checksum"].startswith("sha256:")
    assert metadata["input_spec_checksum"].startswith("sha256:")
    assert prompt not in {value for value in metadata.values()}


def test_stability_prompt_over_the_cap_fails_before_any_post(tmp_path):
    poster = FakePoster(response=FakeResponse(content=mp3_bytes(seconds=3)))
    provider = _provider(tmp_path, poster)
    with pytest.raises(MusicProviderFailureV3) as caught:
        provider.create_task(_request_with(constraints=["x" * 20] * 500))
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert poster.calls == []


def test_stability_cap_matches_the_compiler_dialect_cap():
    assert STABILITY_PROMPT_MAX_LENGTH == PROMPT_MAX_LENGTH[PromptDialect.STABILITY]
    assert PROMPT_MAX_LENGTH[PromptDialect.STABILITY] == 10000

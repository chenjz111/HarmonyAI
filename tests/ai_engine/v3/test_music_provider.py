import asyncio

import pytest

from backend.ai_engine.v3.music_provider import (
    MockMusicGenerationProvider,
    MusicProviderFailureV3,
    ProviderTaskTransitionGuard,
    build_matched_fallback_task,
    build_safe_music_provider_log_fields,
    map_provider_task_to_music_task,
    validate_provider_request_capabilities,
)
from backend.app.schemas.v3.music import (
    AudioAsset,
    MusicProviderCapabilities,
    MusicProviderPolicy,
    MusicGenerationV3Request,
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
        "basis": {
            "diagnosis_id": "diag_test",
            "supporting_fact_ids": ["fev_test"],
        },
    }


def _generation_spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 300,
        "instruments": ["guqin"],
        "ambient_sounds": ["water"],
        "structure": {
            "intro_seconds": 30,
            "main_seconds": 240,
            "outro_seconds": 30,
        },
        "energy_curve": "gentle_decline",
        "forbidden_constraints": ["sharp_high_frequency"],
        "fallback_policy": {"allow_local_matching": True},
    }


def _request() -> ProviderMusicRequest:
    return ProviderMusicRequest(
        provider_request_id="pmr_test",
        generation_spec=_generation_spec(),
        output_format="mp3",
        callback_ref=None,
    )


def _generation_request(*, fallback: str = "local_matching") -> MusicGenerationV3Request:
    return MusicGenerationV3Request(
        schema_version="music_generation_v3.0",
        request_id="mgr_test",
        prescription_id="rx_test",
        idempotency_key="sha256:test-key",
        generation_spec=_generation_spec(),
        provider_policy=MusicProviderPolicy(
            mode="prefer_real_generation",
            fallback=fallback,
        ),
    )


def _capabilities() -> MusicProviderCapabilities:
    return MusicProviderCapabilities(
        max_duration_seconds=600,
        supports_progress=True,
        supports_cancel=True,
        supported_instruments=["guqin", "xiao"],
        supported_formats=["mp3", "wav"],
    )


def _matched_asset() -> AudioAsset:
    return AudioAsset(
        music_ref={"music_id": "asset_matched", "source_type": "matched"},
        title="审核曲库测试音频",
        stream_url="/api/v3/music/assets/asset_matched/stream",
        duration_seconds=300,
        format="mp3",
        checksum="sha256:matched-test",
        tone_profile=_tone_profile("fallback"),
        bpm=60,
        instruments=["guqin"],
    )


def _generated_asset() -> AudioAsset:
    payload = _matched_asset().model_dump(mode="json")
    payload["music_ref"] = {
        "music_id": "asset_generated",
        "source_type": "generated",
    }
    payload["stream_url"] = "/api/v3/music/assets/asset_generated/stream"
    payload["checksum"] = "sha256:generated-test"
    payload["tone_profile"]["status"] = "available"
    return AudioAsset.model_validate(payload)

def test_mock_music_provider_supports_typed_sync_and_async_calls():
    tasks = [
        ProviderTask(
            provider_task_id="provider_task_test",
            status="queued",
            progress_value=None,
            asset_locator=None,
            error_code=None,
        )
    ]
    provider = MockMusicGenerationProvider(tasks=tasks, capabilities=_capabilities())

    created = provider.create_task(_request())
    async_created = asyncio.run(provider.acreate_task(_request()))

    assert created.status == "queued"
    assert async_created.status == "queued"
    assert provider.capabilities() == _capabilities()
    assert provider.health().status == "healthy"
    assert provider.create_calls == 2


@pytest.mark.parametrize(
    ("change", "error_code"),
    [
        ({"duration_seconds": 900}, "GENERATION_DURATION_UNSUPPORTED"),
        ({"instruments": ["suona"]}, "GENERATION_INSTRUMENT_UNSUPPORTED"),
        ({"output_format": "m4a"}, "GENERATION_FORMAT_UNSUPPORTED"),
    ],
)
def test_capability_gate_rejects_unsupported_request(change, error_code):
    request = _request().model_copy(deep=True)
    if "output_format" in change:
        request = request.model_copy(update={"output_format": change["output_format"]})
    else:
        spec = request.generation_spec.model_copy(update=change)
        request = request.model_copy(update={"generation_spec": spec})

    with pytest.raises(MusicProviderFailureV3) as caught:
        validate_provider_request_capabilities(request, _capabilities())

    assert caught.value.error_code == error_code
    assert caught.value.retryable is False


def test_cancelled_provider_task_cannot_transition_back_to_success():
    guard = ProviderTaskTransitionGuard()
    guard.observe(
        ProviderTask(
            provider_task_id="provider_task_test",
            status="running",
            progress_value=None,
            asset_locator=None,
            error_code=None,
        )
    )
    guard.observe(
        ProviderTask(
            provider_task_id="provider_task_test",
            status="cancelled",
            progress_value=None,
            asset_locator=None,
            error_code=None,
        )
    )

    with pytest.raises(MusicProviderFailureV3) as caught:
        guard.observe(
            ProviderTask(
                provider_task_id="provider_task_test",
                status="succeeded",
                progress_value=100,
                asset_locator="provider://private-object",
                error_code=None,
            )
        )

    assert caught.value.error_code == "GENERATION_TASK_STATE_INVALID"


def test_provider_failure_can_build_explicit_reviewed_local_match():
    task = build_matched_fallback_task(
        task_id="task_test",
        request=_generation_request(),
        reason_code="GENERATION_PROVIDER_UNAVAILABLE",
        matched_asset=_matched_asset(),
    )

    assert task.status == "matched_fallback"
    assert task.fallback.applied is True
    assert task.audio_asset.music_ref.source_type == "matched"
    assert task.message == "生成服务暂时不可用，已使用审核曲库匹配"


def test_fallback_is_not_allowed_when_policy_disables_it():
    with pytest.raises(MusicProviderFailureV3) as caught:
        build_matched_fallback_task(
            task_id="task_test",
            request=_generation_request(fallback="none"),
            reason_code="GENERATION_PROVIDER_UNAVAILABLE",
            matched_asset=_matched_asset(),
        )

    assert caught.value.error_code == "GENERATION_FALLBACK_NOT_ALLOWED"


def test_fallback_without_playable_asset_fails_instead_of_fake_success():
    with pytest.raises(MusicProviderFailureV3) as caught:
        build_matched_fallback_task(
            task_id="task_test",
            request=_generation_request(),
            reason_code="GENERATION_PROVIDER_UNAVAILABLE",
            matched_asset=None,
        )

    assert caught.value.error_code == "NO_PLAYABLE_ASSET"


def test_safe_music_provider_log_fields_do_not_include_spec_prompt_or_locator():
    fields = build_safe_music_provider_log_fields(
        request=_request(),
        provider="test-provider",
        model="test-model",
        status="failed",
        latency_ms=50,
        error_code="GENERATION_PROVIDER_UNAVAILABLE",
    )

    rendered = repr(fields).lower()
    assert "generation_spec" not in fields
    assert "prompt" not in rendered
    assert "asset_locator" not in rendered
    assert "guqin" not in rendered
    assert fields["spec_sha256"].startswith("sha256:")

def test_running_provider_task_maps_to_indeterminate_public_progress():
    task = map_provider_task_to_music_task(
        task_id="task_test",
        provider_task=ProviderTask(
            provider_task_id="provider_task_private",
            status="running",
            progress_value=None,
            asset_locator=None,
            error_code=None,
        ),
        generated_asset=None,
    )

    assert task.status == "running"
    assert task.progress is not None
    assert task.progress.indeterminate is True
    assert "provider_task_private" not in task.model_dump_json()


def test_provider_success_requires_materialized_generated_asset():
    provider_task = ProviderTask(
        provider_task_id="provider_task_private",
        status="succeeded",
        progress_value=100,
        asset_locator="provider://private-object",
        error_code=None,
    )

    with pytest.raises(MusicProviderFailureV3) as caught:
        map_provider_task_to_music_task(
            task_id="task_test",
            provider_task=provider_task,
            generated_asset=None,
        )

    assert caught.value.error_code == "GENERATION_ASSET_NOT_READY"

    result = map_provider_task_to_music_task(
        task_id="task_test",
        provider_task=provider_task,
        generated_asset=_generated_asset(),
    )
    assert result.status == "succeeded"
    assert result.audio_asset.music_ref.source_type == "generated"
    assert "provider://private-object" not in result.model_dump_json()


def test_provider_raw_failure_code_is_not_exposed_to_public_task():
    task = map_provider_task_to_music_task(
        task_id="task_test",
        provider_task=ProviderTask(
            provider_task_id="provider_task_private",
            status="failed",
            progress_value=None,
            asset_locator=None,
            error_code="vendor stack trace / secret detail",
        ),
        generated_asset=None,
    )

    assert task.status == "failed"
    assert task.error_code == "GENERATION_PROVIDER_UNAVAILABLE"
    assert "vendor stack" not in task.model_dump_json()

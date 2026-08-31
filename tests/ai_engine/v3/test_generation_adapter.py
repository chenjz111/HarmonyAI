"""Generation provider bundle — env-driven selection, secret-safe default."""

import pytest

from backend.ai_engine.v3.generation_provider_adapter import (
    NotConfiguredMusicProvider,
    build_music_provider_bundle,
)
from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.app.schemas.v3.music import ProviderMusicRequest


def _spec() -> dict[str, object]:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": {
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
            "mapping_version": "test-only-v1",
            "basis": {
                "diagnosis_id": "diag_test",
                "supporting_fact_ids": [],
            },
        },
        "bpm": 60,
        "duration_seconds": 300,
        "instruments": ["guqin"],
        "ambient_sounds": [],
        "structure": {"intro_seconds": 30, "main_seconds": 240, "outro_seconds": 30},
        "energy_curve": "gentle_decline",
        "forbidden_constraints": [],
        "fallback_policy": {"allow_local_matching": True},
    }


def _request() -> ProviderMusicRequest:
    return ProviderMusicRequest(
        provider_request_id="pr_test",
        generation_spec=_spec(),
        output_format="mp3",
        callback_ref=None,
    )


def test_empty_env_builds_not_configured_bundle():
    bundle = build_music_provider_bundle({})
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.health.status == "not_configured"
    assert bundle.health.safe_message is not None


def test_not_configured_provider_raises_stable_failure():
    bundle = build_music_provider_bundle({})
    with pytest.raises(MusicProviderFailureV3) as exc_info:
        bundle.provider.create_task(_request())
    assert exc_info.value.error_code == "PROVIDER_NOT_CONFIGURED"
    assert exc_info.value.retryable is False

    with pytest.raises(MusicProviderFailureV3):
        bundle.provider.get_task("pt_1")
    with pytest.raises(MusicProviderFailureV3):
        bundle.provider.cancel_task("pt_1")


def test_configured_env_keeps_secret_out_of_health_payload():
    bundle = build_music_provider_bundle(
        {
            "MUSIC_PROVIDER": "sunokun",
            "MUSIC_PROVIDER_BASE_URL": "https://internal.example.invalid",
            "MUSIC_PROVIDER_API_KEY": "sk-super-secret-value",
            "MUSIC_PROVIDER_MODEL": "sunokun-melody-v1",
        }
    )
    # a configured-but-unwired environment still degrades instead of faking
    # generation success (concrete adapter awaits the provider Decision Record).
    assert isinstance(bundle.provider, NotConfiguredMusicProvider)
    assert bundle.provider.provider_name == "sunokun"
    assert bundle.health.provider == "sunokun"
    assert bundle.health.model == "sunokun-melody-v1"
    serialized = bundle.health.model_dump_json()
    assert "sk-super-secret-value" not in serialized
    assert "https://internal.example.invalid" not in serialized


def test_not_configured_health_never_fakes_healthy():
    bundle = build_music_provider_bundle({})
    health = bundle.provider.health()
    assert health.status == "not_configured"
    assert health.provider == "unconfigured"

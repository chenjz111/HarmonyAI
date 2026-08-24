from copy import deepcopy

from pydantic import TypeAdapter, ValidationError
import pytest


def _tone_profile(*, status: str = "available") -> dict:
    return {
        "schema_version": "tone_profile_v3.0",
        "status": status,
        "weights": {
            "jiao": 0.16,
            "zhi": 0.24,
            "gong": 0.42,
            "shang": 0.08,
            "yu": 0.10,
        },
        "dominant_tone": "gong",
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "five_tone_mapping_v3.0",
        "basis": {"diagnosis_id": "diag_1", "supporting_fact_ids": ["fev_1"]},
    }


def _generation_spec(*, tone_status: str = "available") -> dict:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(status=tone_status),
        "bpm": 58,
        "duration_seconds": 900,
        "instruments": ["guqin", "xiao"],
        "ambient_sounds": ["water"],
        "structure": {
            "intro_seconds": 60,
            "main_seconds": 720,
            "outro_seconds": 120,
        },
        "energy_curve": "gentle_decline",
        "forbidden_constraints": ["sharp_high_frequency"],
        "fallback_policy": {"allow_local_matching": True},
    }


def test_status_dependent_contracts_publish_discriminated_json_schemas():
    from backend.app.schemas.v3.diagnosis import DiagnosisV3
    from backend.app.schemas.v3.music import MusicTask
    from backend.app.schemas.v3.prescription import ToneProfile

    for schema_type in (DiagnosisV3, ToneProfile, MusicTask):
        schema = TypeAdapter(schema_type).json_schema()
        assert schema["discriminator"]["propertyName"] == "status"


def test_generation_spec_is_provider_neutral_and_duration_is_consistent():
    from backend.app.schemas.v3.prescription import GenerationSpec

    spec = GenerationSpec.model_validate(_generation_spec())
    assert spec.bpm == 58

    invalid_duration = spec.model_dump(mode="json")
    invalid_duration["structure"]["main_seconds"] = 700
    with pytest.raises(ValidationError):
        GenerationSpec.model_validate(invalid_duration)

    with pytest.raises(ValidationError):
        GenerationSpec.model_validate(
            {
                **spec.model_dump(mode="json"),
                "generation_prompt": "make relaxing music",
            }
        )


def test_abstained_diagnosis_can_feed_conservative_prescription():
    from backend.app.schemas.v3.prescription import PrescriptionV3

    payload = {
        "schema_version": "prescription_v3.0",
        "agent_id": "prescription_agent",
        "prescription_id": "rx_1",
        "diagnosis_id": "diag_abstained",
        "status": "success",
        "prescription_mode": "wellness",
        "generation_spec": _generation_spec(tone_status="fallback"),
        "personalization": {
            "applied": False,
            "profile_ref": None,
            "adjustments": [],
        },
        "presentation": {
            "title": "本次音乐生成依据",
            "tone_summary": "采用保守的非诊断音乐方式。",
            "parameter_summaries": ["节奏较慢，适合睡前放松"],
            "personalization_summary": "尚未应用历史偏好。",
        },
    }
    prescription = PrescriptionV3.model_validate(payload)
    assert prescription.prescription_mode == "wellness"
    assert prescription.generation_spec is not None
    assert prescription.generation_spec.tone_profile.status == "fallback"

    withheld = deepcopy(payload)
    withheld["status"] = "withheld"
    withheld["prescription_mode"] = None
    withheld["generation_spec"] = None
    withheld_result = PrescriptionV3.model_validate(withheld)
    assert withheld_result.generation_spec is None


def test_music_task_union_requires_authoritative_asset_for_terminal_success():
    from backend.app.schemas.v3.music import MusicTask

    adapter = TypeAdapter(MusicTask)
    running = adapter.validate_python(
        {
            "task_id": "task_1",
            "status": "running",
            "progress": {
                "value": 50,
                "semantics": "provider_reported_percent",
                "indeterminate": False,
            },
            "message": "正在生成音乐",
            "poll_after_ms": 2000,
            "audio_asset": None,
            "fallback": {"applied": False, "reason_code": None},
            "error_code": None,
        }
    )
    assert running.status == "running"

    invalid_success = running.model_dump(mode="json")
    invalid_success["status"] = "succeeded"
    invalid_success["progress"] = {
        "value": 100,
        "semantics": "provider_reported_percent",
        "indeterminate": False,
    }
    invalid_success["poll_after_ms"] = None
    with pytest.raises(ValidationError):
        adapter.validate_python(invalid_success)


def test_provider_music_request_rejects_provider_prompt_at_public_boundary():
    from backend.app.schemas.v3.music import ProviderMusicRequest

    payload = {
        "provider_request_id": "pmr_1",
        "generation_spec": _generation_spec(),
        "output_format": "mp3",
        "callback_ref": "cb_1",
    }
    request = ProviderMusicRequest.model_validate(payload)
    assert request.output_format == "mp3"

    with pytest.raises(ValidationError):
        ProviderMusicRequest.model_validate(
            {
                **payload,
                "prompt": "provider-specific prompt must stay inside adapter",
            }
        )


def test_feedback_requires_only_change_label_and_rejects_conflicting_adjustments():
    from backend.app.schemas.v3.feedback import FeedbackV3

    minimal = {
        "schema_version": "feedback_v3.0",
        "session_id": "sess_1",
        "music_ref": {"music_id": "asset_1", "source_type": "generated"},
        "pre_state_snapshot": {
            "snapshot_id": "qs_1",
            "source": "player_session",
            "captured_at": "2026-08-22T08:45:00Z",
            "tension": 6,
            "fatigue": 7,
        },
        "post_state": {"change_label": "slightly_better"},
    }
    feedback = FeedbackV3.model_validate(minimal)
    assert feedback.continue_use is None
    assert feedback.liked_features == []
    assert feedback.adjustment_preferences == []

    conflicting = {
        **minimal,
        "adjustment_preferences": ["slower_tempo", "faster_tempo"],
    }
    with pytest.raises(ValidationError):
        FeedbackV3.model_validate(conflicting)

    compatible = FeedbackV3.model_validate(
        {
            **minimal,
            "liked_features": ["guqin_timbre", "gentle_rhythm"],
            "adjustment_preferences": [
                "slower_tempo",
                "change_instruments",
                "shorter_duration",
            ],
        }
    )
    assert len(compatible.adjustment_preferences) == 3


def test_preference_update_cannot_claim_new_version_when_not_applied():
    from backend.app.schemas.v3.feedback import FeedbackV3Output

    output = FeedbackV3Output.model_validate(
        {
            "feedback_id": "fb_1",
            "status": "saved",
            "preference_update": {
                "applied": False,
                "previous_version": 4,
                "new_version": None,
                "changed_fields": [],
            },
            "presentation": {"message": "反馈已保存。"},
        }
    )
    assert output.preference_update.applied is False

    invalid = output.model_dump(mode="json")
    invalid["preference_update"]["new_version"] = 5
    with pytest.raises(ValidationError):
        FeedbackV3Output.model_validate(invalid)

def test_diagnosis_input_rejects_untyped_missing_information():
    from backend.app.schemas.v3.diagnosis import DiagnosisV3Input

    payload = {
        "schema_version": "diagnosis_v3.0",
        "diagnosis_id": "diag_input_1",
        "assessment_ref": {
            "assessment_id": "asmt_1",
            "revision": 2,
            "confirmation_status": "confirmed",
            "safety_status": "clear",
        },
        "organ_profile": {
            "status": "insufficient",
            "weights": None,
            "score_semantics": "relative_evidence_distribution",
        },
        "fact_evidence": [],
        "organ_evidence_links": [],
        "conflicts": [],
        "missing_information": [
            {
                "missing_id": "miss_1",
                "field_code": "sleep_duration",
                "display_question": "最近通常能睡多久？",
                "required_for_diagnosis": False,
                "unexpected": "must be rejected",
            }
        ],
    }
    with pytest.raises(ValidationError):
        DiagnosisV3Input.model_validate(payload)


def test_public_v3_schema_registry_is_machine_executable():
    import backend.app.schemas.v3 as v3

    expected = {
        "UnderstandingV3Request",
        "UnderstandingV3Response",
        "AssessmentV3Request",
        "AssessmentV3Response",
        "DiagnosisV3Input",
        "DiagnosisV3",
        "PrescriptionV3Request",
        "PrescriptionV3",
        "MusicGenerationV3Request",
        "MusicTask",
        "FeedbackV3",
        "FeedbackV3Output",
    }
    assert expected <= set(v3.__all__)
    for name in expected:
        TypeAdapter(getattr(v3, name)).json_schema()

def test_music_provider_capabilities_are_explicit_and_bounded():
    from backend.app.schemas.v3.music import MusicProviderCapabilities

    capabilities = MusicProviderCapabilities.model_validate(
        {
            "max_duration_seconds": 900,
            "supports_progress": True,
            "supports_cancel": True,
            "supported_instruments": ["guqin", "xiao"],
            "supported_formats": ["mp3", "wav"],
        }
    )
    assert capabilities.max_duration_seconds == 900

    with pytest.raises(ValidationError):
        MusicProviderCapabilities.model_validate(
            {
                **capabilities.model_dump(mode="json"),
                "max_duration_seconds": 0,
            }
        )

def test_extended_public_registry_and_frozen_aliases():
    import backend.app.schemas.v3 as v3
    from backend.app.schemas.v3.prescription import PersonalizationAdjustment

    for name in ("ClaimDictionaryEntry", "MusicProviderCapabilities"):
        assert name in v3.__all__
        TypeAdapter(getattr(v3, name)).json_schema()

    adjustment = PersonalizationAdjustment.model_validate(
        {
            "field": "instruments",
            "from": "dizi",
            "to": "guqin",
            "reason_code": "USER_PREFERENCE",
        }
    )
    assert adjustment.model_dump(mode="json", by_alias=True)["from"] == "dizi"
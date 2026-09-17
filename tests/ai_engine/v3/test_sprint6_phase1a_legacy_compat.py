"""Sprint 6 Phase 1A — legacy compatibility regression suite (blocking-fix F1/F2/F3/F5).

Covers the Owner decision matrix:

| legacy condition | expected compatibility result |
|---|---|
| diagnosis abstained | ``basic_wellness`` |
| prescription mode known ``wellness`` | ``basic_wellness`` |
| known historical fabricated-Gong fallback | ``basic_wellness`` |
| successful non-abstained syndrome-based row with real tone authority | ``personalized_five_tone`` |
| missing/contradictory provenance | explicit ``legacy_unclassified`` (fail closed) |
| provider/schema/checksum/readiness failure | failure — never a music mode |

Also covers pre-Phase-1A checksum integrity and the "no epsilon" exact-tie rule.
"""

from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from backend.ai_engine.v3.agent3 import (
    build_five_tone_analysis_v31,
    build_generation_spec_v31,
    build_tone_profile_v31,
)
from backend.app.schemas.v3.flow_v31 import (
    FiveToneAnalysisReadModel,
    ToneProfileV31,
)
from backend.app.services.v3 import legacy_mode_compat as compat
from backend.app.services.v3.legacy_mode_compat import (
    LegacyModeUnclassifiedError,
    LegacyProvenance,
)

TONE_CODES = ("jiao", "zhi", "gong", "shang", "yu")
FABRICATED_WEIGHTS = {"jiao": 0.1, "zhi": 0.1, "gong": 0.6, "shang": 0.1, "yu": 0.1}


# --------------------------------------------------------------------------- #
# pre-Phase-1A payload builders (the stored legacy representations)
# --------------------------------------------------------------------------- #


def _legacy_tone_profile(
    *,
    weights: dict[str, float] | None = None,
    primary_tone: str = "gong",
    evidence_refs: tuple[str, ...] = ("fev_legacy",),
) -> dict:
    return {
        "schema_version": "tone_profile_v3.1",
        "weights": dict(weights or FABRICATED_WEIGHTS),
        "primary_tone": primary_tone,
        "secondary_tone": None,
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "tone_mapping_v3.0",
        "basis": {
            "diagnosis_id": "diag_legacy",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": list(evidence_refs),
        },
    }


def _legacy_read_model(
    *,
    primary_tone: str | None = "gong",
    evidence_refs: tuple[str, ...] = ("assessment:asmt_legacy:r1",),
) -> dict:
    return {
        "schema_version": "five_tone_analysis_read_model_v3.1",
        "confirmed_user_state_ref": {
            "confirmed_user_state_id": "cus_legacy",
            "revision": 1,
            "content_checksum": "sha256:cus-legacy",
        },
        "confirmed_state": "legacy confirmed state",
        "state_tendency": "legacy tendency",
        "analysis_rationales": [
            {"summary": "legacy basis", "evidence_refs": list(evidence_refs)}
        ],
        "primary_tone": (
            {"tone": primary_tone, "display_name": "宫调", "explanation": "legacy"}
            if primary_tone is not None
            else None
        ),
        "secondary_tone": None,
        "bpm": {"value": 62, "explanation": "approved bpm"},
        "instruments": {"values": ["guqin"], "explanation": "approved instruments"},
        "ambience": {"values": ["water"], "explanation": "approved ambience"},
        "duration": {"seconds": 180, "explanation": "approved duration"},
        "generation": {"status": "ready", "message": "ready"},
        "disclaimer": "本结果不构成医学诊断或治疗建议。",
    }


def _legacy_transport_spec(tone_profile: dict) -> dict:
    return {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": tone_profile,
        "bpm": 62,
        "duration_seconds": 180,
        "instruments": ["guqin"],
        "ambient_sounds": [],
        "structure": {"intro_seconds": 10, "main_seconds": 160, "outro_seconds": 10},
        "energy_curve": "平稳舒缓",
        "forbidden_constraints": [],
        "fallback_policy": {"allow_local_matching": True},
    }


# --------------------------------------------------------------------------- #
# 0. schema validators must not invent a mode
# --------------------------------------------------------------------------- #


def test_schema_validators_reject_legacy_payloads_instead_of_guessing():
    with pytest.raises(ValidationError):
        ToneProfileV31.model_validate(_legacy_tone_profile())
    with pytest.raises(ValidationError):
        FiveToneAnalysisReadModel.model_validate(_legacy_read_model())


# --------------------------------------------------------------------------- #
# 1. genuine legacy personalized row
# --------------------------------------------------------------------------- #


def test_genuine_legacy_personalized_row_stays_personalized():
    profile = _legacy_tone_profile(
        weights={"jiao": 0.10, "zhi": 0.20, "gong": 0.55, "shang": 0.10, "yu": 0.05},
        evidence_refs=("fev_real_1", "fev_real_2"),
    )
    resolved, meta = compat.resolve_tone_profile_payload(
        profile,
        LegacyProvenance(
            source="diagnosis",
            diagnosis_status="success",
            abstain_reason=None,
        ),
    )
    assert meta is not None
    assert meta.compatibility_state == "legacy_derived"
    assert meta.reason_code == compat.LEGACY_REASON_GENUINE_PERSONALIZED
    assert resolved.regulation_mode == "personalized_five_tone"
    assert resolved.primary_tone is not None
    assert resolved.primary_tone.value == "gong"
    assert resolved.weights is not None
    assert resolved.schema_version == "tone_profile_v3.2"


# --------------------------------------------------------------------------- #
# 2. legacy wellness row (prescription mode is the reliable signal)
# --------------------------------------------------------------------------- #


def test_legacy_wellness_prescription_row_resolves_to_basic_wellness():
    profile = _legacy_tone_profile(evidence_refs=())
    resolved, meta = compat.resolve_tone_profile_payload(
        profile,
        LegacyProvenance(source="prescription", prescription_mode="wellness"),
    )
    assert meta is not None
    assert meta.reason_code == compat.LEGACY_REASON_WELLNESS_PRESCRIPTION
    assert resolved.regulation_mode == "basic_wellness"
    assert resolved.primary_tone is None
    assert resolved.weights is None
    # the fabricated Gong must not survive the projection
    assert resolved.regulation_mode != "personalized_five_tone"


# --------------------------------------------------------------------------- #
# 3. legacy abstained diagnosis
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("status", "abstain_reason"),
    [("abstained", "ELEMENT_EVIDENCE_INSUFFICIENT"), ("abstained", "RAG_EMPTY")],
)
def test_legacy_abstained_diagnosis_resolves_to_basic_wellness(status, abstain_reason):
    profile = _legacy_tone_profile(weights=FABRICATED_WEIGHTS, evidence_refs=())
    resolved, meta = compat.resolve_tone_profile_payload(
        profile,
        LegacyProvenance(
            source="diagnosis",
            diagnosis_status=status,
            abstain_reason=abstain_reason,
        ),
    )
    assert meta is not None
    assert meta.reason_code == compat.LEGACY_REASON_ABSTAINED
    assert resolved.regulation_mode == "basic_wellness"
    assert resolved.primary_tone is None


def test_legacy_abstained_read_model_loses_the_fabricated_tone_claim():
    stored = _legacy_read_model(primary_tone="gong")
    resolved, meta = compat.resolve_read_model_payload(
        stored,
        LegacyProvenance(
            source="diagnosis",
            diagnosis_status="abstained",
            abstain_reason="RAG_EMPTY",
        ),
    )
    assert meta is not None
    assert resolved.regulation_mode == "basic_wellness"
    assert resolved.primary_tone is None
    assert resolved.tone_weights is None
    assert resolved.schema_version == "five_tone_analysis_read_model_v3.2"


# --------------------------------------------------------------------------- #
# 4. legacy fabricated-Gong fallback (signature detection, no row context)
# --------------------------------------------------------------------------- #


def test_known_fabricated_gong_fallback_never_becomes_personalized():
    profile = _legacy_tone_profile(weights=FABRICATED_WEIGHTS, evidence_refs=())
    for provenance in (
        LegacyProvenance(source="asset"),
        LegacyProvenance(source="diagnosis", diagnosis_status="success"),
        LegacyProvenance(source="prescription", prescription_mode="syndrome_based"),
    ):
        resolved, meta = compat.resolve_tone_profile_payload(profile, provenance)
        assert meta is not None
        assert meta.reason_code == compat.LEGACY_REASON_FABRICATED_FALLBACK
        assert resolved.regulation_mode == "basic_wellness"
        assert resolved.primary_tone is None
        assert resolved.weights is None


def test_fabricated_signature_helper_is_exact():
    assert compat.is_known_fabricated_fallback(FABRICATED_WEIGHTS)
    assert not compat.is_known_fabricated_fallback(
        {**FABRICATED_WEIGHTS, "gong": 0.61}
    )
    assert not compat.is_known_fabricated_fallback(None)
    assert not compat.is_known_fabricated_fallback({"gong": 1.0})


# --------------------------------------------------------------------------- #
# 5. ambiguous legacy row → explicit unclassified / fail closed
# --------------------------------------------------------------------------- #


def test_ambiguous_legacy_row_fails_closed_without_a_mode():
    # Non-fabricated distribution but no reliable provenance information.
    profile = _legacy_tone_profile(
        weights={tone: (0.6 if tone == "jiao" else 0.1) for tone in TONE_CODES},
        primary_tone="jiao",
        evidence_refs=(),
    )
    meta = compat.classify_legacy_mode(
        weights=profile["weights"],
        evidence_refs=profile["basis"]["supporting_evidence_refs"],
        provenance=LegacyProvenance(source="asset"),
    )
    assert meta.compatibility_state == "legacy_unclassified"
    assert meta.reason_code == compat.LEGACY_REASON_UNCLASSIFIED
    assert meta.regulation_mode is None
    assert meta.is_unclassified is True

    # fail closed: no tone-bearing projection is produced for an ambiguous row
    with pytest.raises(LegacyModeUnclassifiedError):
        compat.resolve_tone_profile_payload(
            profile, LegacyProvenance(source="asset")
        )


def test_ambiguous_legacy_row_raises_for_read_model_projection():
    # A tone-bearing read model whose row context contradicts a real conclusion
    # (withheld/failed diagnosis) must not be projected as personalized.
    stored = _legacy_read_model(primary_tone="jiao")
    with pytest.raises(LegacyModeUnclassifiedError) as error:
        compat.resolve_read_model_payload(
            stored,
            LegacyProvenance(source="diagnosis", diagnosis_status="withheld"),
        )
    assert error.value.error_code == compat.LEGACY_UNCLASSIFIED_CODE


def test_legacy_resolution_never_invents_integrated_regulation():
    """Sprint 5 had no integrated mode, so it is never derived from old data."""

    cases = [
        (
            _legacy_tone_profile(evidence_refs=()),
            LegacyProvenance(source="prescription", prescription_mode="wellness"),
        ),
        (
            _legacy_tone_profile(
                weights={tone: (0.6 if tone == "jiao" else 0.1) for tone in TONE_CODES},
                primary_tone="jiao",
            ),
            LegacyProvenance(source="diagnosis", diagnosis_status="success"),
        ),
        (
            _legacy_tone_profile(evidence_refs=()),
            LegacyProvenance(source="diagnosis", diagnosis_status="abstained"),
        ),
    ]
    for profile, provenance in cases:
        resolved, _meta = compat.resolve_tone_profile_payload(profile, provenance)
        assert resolved.regulation_mode != "integrated_regulation"


# --------------------------------------------------------------------------- #
# 6. pre-Phase-1A persisted read-model checksum verification
# --------------------------------------------------------------------------- #


def test_stored_legacy_checksum_verifies_against_the_stored_representation():
    stored = _legacy_read_model()
    checksum = compat.payload_checksum(stored)
    assert compat.stored_checksum_matches(stored, checksum)

    # the derived compatibility view is NOT the stored payload and must never be
    # verified against the stored checksum
    derived, _meta = compat.resolve_read_model_payload(
        stored,
        LegacyProvenance(
            source="diagnosis",
            diagnosis_status="success",
            abstain_reason=None,
        ),
        tone_weights={"jiao": 0.10, "zhi": 0.20, "gong": 0.55, "shang": 0.10, "yu": 0.05},
    )
    derived_payload = derived.model_dump(mode="json")
    assert derived_payload != stored
    assert not compat.stored_checksum_matches(derived_payload, checksum)


def test_legacy_read_does_not_mutate_the_stored_payload():
    stored = _legacy_read_model()
    before = copy.deepcopy(stored)
    checksum = compat.payload_checksum(stored)
    compat.resolve_read_model_payload(
        stored,
        LegacyProvenance(source="diagnosis", diagnosis_status="abstained"),
    )
    assert stored == before
    assert compat.payload_checksum(stored) == checksum


def test_tampered_legacy_payload_fails_checksum_verification():
    stored = _legacy_read_model()
    checksum = compat.payload_checksum(stored)
    tampered = copy.deepcopy(stored)
    tampered["state_tendency"] = "tampered"
    assert not compat.stored_checksum_matches(tampered, checksum)


def test_legacy_checksum_matches_the_pre_phase_1a_persistence_rule():
    """The pre-1A rule was sha256 over the compact sorted JSON of the payload."""

    stored = _legacy_read_model()
    expected = "sha256:" + __import__("hashlib").sha256(
        json.dumps(
            stored, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    assert compat.payload_checksum(stored) == expected


# --------------------------------------------------------------------------- #
# 7. pre-Phase-1A persisted generation / prescription compatibility
# --------------------------------------------------------------------------- #


def test_legacy_wellness_transport_spec_resolves_to_basic_wellness():
    spec, meta = compat.resolve_generation_spec_payload(
        _legacy_transport_spec(_legacy_tone_profile(evidence_refs=())),
        LegacyProvenance(source="prescription", prescription_mode="wellness"),
    )
    assert meta is not None
    assert spec.tone_profile.regulation_mode == "basic_wellness"
    assert spec.tone_profile.primary_tone is None
    assert spec.tone_profile.weights is None
    # approved non-tone parameters survive the compatibility projection
    assert spec.bpm == 62
    assert spec.duration_seconds == 180
    assert spec.instruments == ["guqin"]


def test_legacy_genuine_transport_spec_keeps_its_real_tone_authority():
    spec, meta = compat.resolve_generation_spec_payload(
        _legacy_transport_spec(
            _legacy_tone_profile(
                weights={tone: (0.6 if tone == "jiao" else 0.1) for tone in TONE_CODES},
                primary_tone="jiao",
                evidence_refs=("fev_real_1",),
            )
        ),
        LegacyProvenance(
            source="prescription",
            prescription_mode="syndrome_based",
        ),
    )
    assert meta is not None
    assert meta.reason_code == compat.LEGACY_REASON_GENUINE_PERSONALIZED
    assert spec.tone_profile.regulation_mode == "personalized_five_tone"
    assert spec.tone_profile.primary_tone is not None
    assert spec.tone_profile.primary_tone.value == "jiao"


def test_modern_payloads_still_take_the_modern_path():
    payload = {
        "schema_version": "tone_profile_v3.2",
        "regulation_mode": "integrated_regulation",
        "weights": {tone: 0.2 for tone in TONE_CODES},
        "primary_tone": None,
        "secondary_tone": None,
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "five_tone_mapping_v3@3.0.0",
        "basis": {
            "diagnosis_id": "diag_new",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": ["fev_1"],
        },
    }
    resolved, meta = compat.resolve_tone_profile_payload(
        payload, LegacyProvenance(source="diagnosis")
    )
    assert meta is None
    assert resolved.regulation_mode == "integrated_regulation"


def test_unknown_schema_version_is_rejected_not_guessed():
    with pytest.raises(ValueError, match=compat.UNSUPPORTED_SCHEMA_VERSION):
        compat.resolve_tone_profile_payload(
            {"schema_version": "tone_profile_v9.9"},
            LegacyProvenance(source="diagnosis"),
        )


# --------------------------------------------------------------------------- #
# 8. canonical authority + no-epsilon exact tie
# --------------------------------------------------------------------------- #


def _mapping() -> dict:
    return {
        "schema_id": "five_tone_mapping_v3",
        "schema_version": "3.0.0",
        "organ_tone_weights": {
            "primary": {
                "liver": {"jiao": 1.0},
                "heart": {"zhi": 1.0},
                "spleen": {"gong": 1.0},
                "lung": {"shang": 1.0},
                "kidney": {"yu": 1.0},
            }
        },
        "organ_tone_table": [{"tone": tone, "tone_cn": tone} for tone in TONE_CODES],
    }


def test_canonical_authority_matches_across_spec_and_read_model():
    profile = build_tone_profile_v31(
        diagnosis_id="diag_authority",
        diagnosis_status="success",
        organ_weights={
            "spleen": 0.7,
            "liver": 0.1,
            "heart": 0.1,
            "lung": 0.05,
            "kidney": 0.05,
        },
        supporting_evidence_refs=["fev_1"],
        mapping=_mapping(),
    )
    rules = {
        "schema_id": "music_generation_rules_v3.1",
        "schema_version": "test-approved-v1",
        "asset_version": "owner-approved-test-v1",
        "review_status": "approved",
        "secondary_goal_merge_policy": "primary_over_secondary_fill_missing",
        "default": {
            "bpm": 60,
            "instruments": ["guqin"],
            "ambience": ["water"],
            "duration_seconds": 180,
            "explanations": {
                "bpm": "b",
                "instruments": "i",
                "ambience": "a",
                "duration": "d",
            },
        },
        "goals": {
            "sleep": {},
            "relaxation": {},
            "emotion_regulation": {},
            "focus": {},
            "energy": {},
            "stress_relief": {},
            "other": {},
        },
    }
    spec = build_generation_spec_v31(profile=profile, parameter_rules=rules)
    read_model = build_five_tone_analysis_v31(
        confirmed_user_state_ref={
            "confirmed_user_state_id": "cus_1",
            "revision": 1,
            "content_checksum": "sha256:cus",
        },
        confirmed_state="state",
        state_tendency="tendency",
        profile=profile,
        evidence_refs=["fev_1"],
        mapping=_mapping(),
        generation_spec=spec,
    )
    assert (
        profile.regulation_mode
        == spec.regulation_mode
        == read_model.regulation_mode
        == "personalized_five_tone"
    )


def test_exact_tie_uses_canonical_precision_without_an_epsilon():
    """Canonical exact tie → integrated; a near (non-exact) tie is not invented."""

    uniform = {name: 0.2 for name in ("liver", "heart", "spleen", "lung", "kidney")}
    tied = build_tone_profile_v31(
        diagnosis_id="diag_tie",
        diagnosis_status="success",
        organ_weights=uniform,
        supporting_evidence_refs=["fev_1"],
        mapping=_mapping(),
    )
    assert tied.regulation_mode == "integrated_regulation"
    assert tied.primary_tone is None
    assert tied.weights is not None

    # identical tone weights except one tone marginally higher: canonical
    # equality does not hold, and Phase 1A introduces no ambiguity epsilon.
    near = build_tone_profile_v31(
        diagnosis_id="diag_near",
        diagnosis_status="success",
        organ_weights={
            "liver": 0.2001,
            "heart": 0.2,
            "spleen": 0.2,
            "lung": 0.2,
            "kidney": 0.1999,
        },
        supporting_evidence_refs=["fev_1"],
        mapping=_mapping(),
    )
    assert near.regulation_mode == "personalized_five_tone"
    assert near.primary_tone is not None

"""Sprint 6 Phase 5 — Prompt Compiler V2 golden tests (PC1..PC22).

The compiler is pure and deterministic, so every case here is an offline golden
assertion: no provider, no network, no database.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from backend.ai_engine.v3.music_provider import MusicProviderFailureV3
from backend.ai_engine.v3.prompt_compiler import (
    CANONICAL_MUSIC_PROMPT_VERSION,
    PROMPT_COMPILER_VERSION,
    PROMPT_MAX_LENGTH,
    TONE_DESCRIPTOR_VERSION,
    TONE_PROMPT_DESCRIPTORS,
    PromptCompilerContractError,
    PromptDialect,
    build_canonical_prompt,
    compile_music_prompt,
    input_spec_checksum,
)
from backend.app.schemas.v3.music import ProviderMusicRequest

ALL_DIALECTS = tuple(PromptDialect)
TONE_CODES = ("jiao", "zhi", "gong", "shang", "yu")


def _tone_profile(**overrides):
    payload = {
        "schema_version": "tone_profile_v3.2",
        "regulation_mode": "personalized_five_tone",
        "weights": {
            "jiao": 0.7,
            "zhi": 0.15,
            "gong": 0.05,
            "shang": 0.05,
            "yu": 0.05,
        },
        "primary_tone": "jiao",
        "secondary_tone": "zhi",
        "score_semantics": "relative_tone_distribution",
        "mapping_version": "test-only-v1",
        "basis": {
            "diagnosis_id": "diag_pc",
            "diagnosis_revision": 1,
            "supporting_evidence_refs": ["fev_pc"],
        },
    }
    payload.update(overrides)
    return payload


def _generation_spec(**overrides):
    payload = {
        "schema_version": "generation_spec_v3.0",
        "tone_profile": _tone_profile(),
        "bpm": 60,
        "duration_seconds": 60,
        "instruments": ["guqin", "xiao"],
        "ambient_sounds": ["water"],
        "structure": {"intro_seconds": 6, "main_seconds": 48, "outro_seconds": 6},
        "energy_curve": "gentle_decline",
        "forbidden_constraints": [],
        "fallback_policy": {"allow_local_matching": True},
    }
    payload.update(overrides)
    return payload


def spec(**overrides):
    """Validated authoritative GenerationSpec built from a dict payload."""

    return ProviderMusicRequest(
        provider_request_id="pr_pc",
        generation_spec=_generation_spec(**overrides),  # type: ignore[arg-type]
        output_format="mp3",
        callback_ref=None,
    ).generation_spec


def compile_for(dialect: PromptDialect, **overrides):
    return compile_music_prompt(spec(**overrides), dialect)


# --------------------------------------------------------------------------- #
# PC1 / PC2 / PC3 — tone and weight rendering
# --------------------------------------------------------------------------- #
def test_pc1_primary_tone_only_renders_descriptor_without_raw_enum():
    compiled = compile_for(
        PromptDialect.TOKENHUB_MINIMAX,
        tone_profile=_tone_profile(secondary_tone=None),
    )
    assert TONE_PROMPT_DESCRIPTORS["jiao"] in compiled.text
    assert "primary tone emphasis 0.7" in compiled.text
    assert "secondary" not in compiled.text
    assert not re.search(r"\bjiao\b", compiled.text, re.IGNORECASE)


def test_pc2_primary_and_secondary_render_both_authoritative_weights():
    compiled = compile_for(PromptDialect.MINIMAX)
    assert TONE_PROMPT_DESCRIPTORS["jiao"] in compiled.text
    assert TONE_PROMPT_DESCRIPTORS["zhi"] in compiled.text
    assert "primary tone emphasis 0.7" in compiled.text
    assert "secondary warm, lively melodic contour emphasis 0.15" in compiled.text
    for tone in ("jiao", "zhi"):
        assert not re.search(rf"\b{tone}\b", compiled.text, re.IGNORECASE)


def test_pc2b_exact_weight_values_are_preserved_not_renormalized():
    weights = {
        "jiao": 0.5455,
        "zhi": 0.4545,
        "gong": 0.0,
        "shang": 0.0,
        "yu": 0.0,
    }
    compiled = compile_for(
        PromptDialect.STABILITY,
        tone_profile=_tone_profile(weights=weights, secondary_tone="zhi"),
    )
    assert "primary tone emphasis 0.5455" in compiled.text
    assert "secondary warm, lively melodic contour emphasis 0.4545" in compiled.text


def test_pc2c_missing_authoritative_weight_fails_closed():
    # Bypass schema validation deliberately: this models a caller handing the
    # compiler an incomplete authoritative profile (the guard must fail closed
    # rather than invent, renormalize or silently drop a weight).
    incomplete = SimpleNamespace(
        tone_profile=SimpleNamespace(
            regulation_mode="personalized_five_tone",
            primary_tone="jiao",
            secondary_tone=None,
            weights={"zhi": 0.15, "gong": 0.05, "shang": 0.05, "yu": 0.05},
        ),
        bpm=60,
        duration_seconds=60,
        instruments=["guqin"],
        ambient_sounds=[],
        structure=SimpleNamespace(
            intro_seconds=6, main_seconds=48, outro_seconds=6
        ),
        energy_curve="gentle_decline",
        forbidden_constraints=[],
    )
    with pytest.raises(MusicProviderFailureV3) as caught:
        compile_music_prompt(incomplete, PromptDialect.MINIMAX)
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert isinstance(caught.value.cause, PromptCompilerContractError)
    assert caught.value.cause.reason_code == "PROMPT_COMPILER_TONE_WEIGHT_MISSING"


def test_pc2d_secondary_tone_without_weight_fails_closed():
    incomplete = SimpleNamespace(
        tone_profile=SimpleNamespace(
            regulation_mode="personalized_five_tone",
            primary_tone="jiao",
            secondary_tone="zhi",
            weights={"jiao": 0.7},
        ),
        bpm=60,
        duration_seconds=60,
        instruments=["guqin"],
        ambient_sounds=[],
        structure=SimpleNamespace(
            intro_seconds=6, main_seconds=48, outro_seconds=6
        ),
        energy_curve="gentle_decline",
        forbidden_constraints=[],
    )
    with pytest.raises(MusicProviderFailureV3) as caught:
        compile_music_prompt(incomplete, PromptDialect.TOKENHUB_MINIMAX)
    assert caught.value.cause.reason_code == "PROMPT_COMPILER_TONE_WEIGHT_MISSING"


@pytest.mark.parametrize(
    "tone,expected_weight",
    (("jiao", "0.7"), ("zhi", "0.15"), ("gong", "0.05"), ("shang", "0.05"), ("yu", "0.05")),
)
def test_pc3_all_five_tones_render_provider_safe_descriptors(tone, expected_weight):
    for dialect in ALL_DIALECTS:
        compiled = compile_for(
            dialect,
            tone_profile=_tone_profile(primary_tone=tone, secondary_tone=None),
        )
        assert TONE_PROMPT_DESCRIPTORS[tone] in compiled.text
        assert f"primary tone emphasis {expected_weight}" in compiled.text
        assert not re.search(rf"\b{tone}\b", compiled.text, re.IGNORECASE)


def test_pc3b_integrated_and_basic_keep_the_authoritative_distribution_visible():
    integrated = _tone_profile(
        regulation_mode="integrated_regulation",
        primary_tone=None,
        secondary_tone=None,
        weights={tone: 0.2 for tone in TONE_CODES},
    )
    compiled = compile_for(PromptDialect.TOKENHUB_MINIMAX, tone_profile=integrated)
    assert "balanced five-tone blend without a dominant tone" in compiled.text
    assert "neutral five-tone distribution retained" in compiled.text
    for tone in TONE_CODES:
        assert not re.search(rf"\b{tone}\b", compiled.text, re.IGNORECASE)

    basic = _tone_profile(
        regulation_mode="basic_wellness",
        primary_tone=None,
        secondary_tone=None,
        weights=None,
    )
    compiled_basic = compile_for(PromptDialect.MINIMAX, tone_profile=basic)
    assert "neutral, gentle soundscape without a tone conclusion" in compiled_basic.text
    assert "neutral five-tone distribution retained" not in compiled_basic.text


# --------------------------------------------------------------------------- #
# PC4 / PC5 / PC6 — instrument normalization
# --------------------------------------------------------------------------- #
def test_pc4_approved_chinese_instrument_alias_normalizes_for_every_dialect():
    for dialect in ALL_DIALECTS:
        compiled = compile_for(dialect, instruments=["古琴", "箫"])
        assert "Instruments: guqin, xiao" in compiled.text
        assert "古琴" not in compiled.text


def test_pc4b_rule_asset_chinese_names_normalize_to_canonical_tokens():
    compiled = compile_for(
        PromptDialect.STABILITY, instruments=["古琴", "琵琶", "笛", "埙"]
    )
    assert "Instruments: guqin, pipa, dizi, xun" in compiled.text


def test_pc5_unsupported_instrument_fails_closed_before_any_call():
    for dialect in ALL_DIALECTS:
        with pytest.raises(MusicProviderFailureV3) as caught:
            compile_for(dialect, instruments=["suona"])
        assert caught.value.error_code == "GENERATION_INSTRUMENT_UNSUPPORTED"
        assert caught.value.retryable is False


def test_pc6_mixed_known_and_unknown_instruments_fail_as_a_whole():
    with pytest.raises(MusicProviderFailureV3) as caught:
        compile_for(PromptDialect.MINIMAX, instruments=["古琴", "唢呐"])
    assert caught.value.error_code == "GENERATION_INSTRUMENT_UNSUPPORTED"


def test_pc6b_unsupported_raw_value_never_leaks_into_the_prompt():
    with pytest.raises(MusicProviderFailureV3):
        compile_for(PromptDialect.TOKENHUB_MINIMAX, instruments=["guqin", "theremin"])


def test_pc6c_repeated_approved_instrument_collapses_without_reordering():
    compiled = compile_for(
        PromptDialect.MINIMAX, instruments=["古琴", "guqin", "箫"]
    )
    assert "Instruments: guqin, xiao" in compiled.text


# --------------------------------------------------------------------------- #
# PC7 / PC8 / PC9 — ambience normalization
# --------------------------------------------------------------------------- #
def test_pc7_real_ambience_renders():
    for dialect in ALL_DIALECTS:
        compiled = compile_for(dialect, ambient_sounds=["water"])
        assert "Atmosphere: soft water ambience." in compiled.text


@pytest.mark.parametrize(
    "token", ["无额外环境音", "无其他环境音", "无环境音", "no_extra_ambient", "no_ambient", "none"]
)
def test_pc8_no_extra_ambient_never_renders_a_contradictory_fragment(token):
    for dialect in ALL_DIALECTS:
        compiled = compile_for(dialect, ambient_sounds=[token])
        assert token not in compiled.text
        assert "ambience" not in compiled.text
        assert "Atmosphere" not in compiled.text


def test_pc9_mixed_real_ambience_and_no_ambient_token_is_not_contradictory():
    for dialect in ALL_DIALECTS:
        compiled = compile_for(dialect, ambient_sounds=["无额外环境音", "water"])
        assert "Atmosphere: soft water ambience." in compiled.text
        assert "无额外环境音" not in compiled.text
        assert "soft 无额外环境音 ambience" not in compiled.text


# --------------------------------------------------------------------------- #
# PC10 / PC11 / PC12 / PC13 / PC14 — authoritative parameters
# --------------------------------------------------------------------------- #
def test_pc10_bpm_is_rendered_from_the_spec():
    for dialect in ALL_DIALECTS:
        assert "bpm 72" in compile_for(dialect, bpm=72).text


def test_pc11_duration_target_is_dialect_specific_and_authoritative():
    structure = {"intro_seconds": 6, "main_seconds": 78, "outro_seconds": 6}
    tokenhub = compile_for(
        PromptDialect.TOKENHUB_MINIMAX, duration_seconds=90, structure=structure
    )
    assert "target length about 90 seconds" in tokenhub.text
    for dialect in (PromptDialect.MINIMAX, PromptDialect.STABILITY):
        compiled = compile_for(dialect, duration_seconds=90, structure=structure)
        assert "total duration 90 seconds" in compiled.text


def test_pc12_structure_is_rendered_exactly():
    compiled = compile_for(
        PromptDialect.MINIMAX,
        duration_seconds=90,
        structure={"intro_seconds": 6, "main_seconds": 78, "outro_seconds": 6},
    )
    assert "Structure: intro 6s, main 78s, outro 6s" in compiled.text


def test_pc13_energy_curve_is_rendered_verbatim():
    for dialect in ALL_DIALECTS:
        assert "Energy: 平稳舒缓" in compile_for(dialect, energy_curve="平稳舒缓").text


def test_pc14_empty_forbidden_constraints_produce_no_avoid_fragment():
    for dialect in ALL_DIALECTS:
        compiled = compile_for(dialect, forbidden_constraints=[])
        assert "Avoid:" not in compiled.text


def test_pc14b_legal_forbidden_constraints_are_rendered_verbatim():
    compiled = compile_for(
        PromptDialect.TOKENHUB_MINIMAX, forbidden_constraints=["sharp_high_frequency"]
    )
    assert "Avoid: sharp_high_frequency." in compiled.text


# --------------------------------------------------------------------------- #
# PC15 / PC16 — prompt length
# --------------------------------------------------------------------------- #
def _long_constraints(total_chars: int) -> list[str]:
    chunk = "x" * 20
    return [chunk] * max(1, total_chars // 21)


def test_pc15_prompt_near_max_length_still_compiles():
    compiled = compile_for(
        PromptDialect.TOKENHUB_MINIMAX, forbidden_constraints=_long_constraints(1500)
    )
    assert len(compiled.text) <= PROMPT_MAX_LENGTH[PromptDialect.TOKENHUB_MINIMAX]
    assert len(compiled.text) > 1400


def test_pc16_prompt_over_max_length_fails_closed_per_dialect():
    for dialect in ALL_DIALECTS:
        overflow = PROMPT_MAX_LENGTH[dialect] + 500
        with pytest.raises(MusicProviderFailureV3) as caught:
            compile_for(dialect, forbidden_constraints=_long_constraints(overflow))
        assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
        assert caught.value.retryable is False


def test_pc16b_stability_has_a_larger_cap_than_the_other_dialects():
    assert PROMPT_MAX_LENGTH[PromptDialect.STABILITY] == 10000
    assert PROMPT_MAX_LENGTH[PromptDialect.TOKENHUB_MINIMAX] == 2000
    assert PROMPT_MAX_LENGTH[PromptDialect.MINIMAX] == 2000


# --------------------------------------------------------------------------- #
# PC17 / PC18 / PC19 / PC22 — determinism and identity
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("dialect", ALL_DIALECTS)
def test_pc17_pc18_pc22_repeat_compilation_is_byte_identical(dialect):
    first = compile_for(dialect)
    second = compile_for(dialect)
    assert first.text == second.text
    assert first.checksum == second.checksum
    assert first.input_spec_checksum == second.input_spec_checksum
    assert first.audit_identity() == second.audit_identity()


def test_pc19_dialect_identity_is_distinct_and_losslessly_persistable():
    seen = set()
    for dialect in ALL_DIALECTS:
        compiled = compile_for(dialect)
        assert compiled.dialect_id == dialect.value
        assert compiled.compiler_version == PROMPT_COMPILER_VERSION
        assert CANONICAL_MUSIC_PROMPT_VERSION  # documented model version
        # The audit identity is persisted as separate JSON fields (no composite
        # string is packed into a length-limited column), so every value is
        # stored losslessly.
        identity = compiled.audit_identity()
        assert identity["dialect_id"] == dialect.value
        assert identity["compiler_version"] == PROMPT_COMPILER_VERSION
        assert len(identity["prompt_checksum"]) == len("sha256:") + 64
        seen.add(compiled.dialect_id)
    assert seen == {dialect.value for dialect in ALL_DIALECTS}


def test_pc19b_input_spec_checksum_ignores_run_identity():
    first = compile_for(PromptDialect.MINIMAX)
    second = compile_for(PromptDialect.TOKENHUB_MINIMAX)
    # Same authoritative spec, different dialect => same input identity.
    assert first.input_spec_checksum == second.input_spec_checksum
    assert first.checksum != second.checksum


def test_pc19c_audit_identity_carries_exactly_the_four_fields():
    identity = compile_for(PromptDialect.STABILITY).audit_identity()
    assert set(identity) == {
        "compiler_version",
        "dialect_id",
        "prompt_checksum",
        "input_spec_checksum",
    }
    assert identity["prompt_checksum"].startswith("sha256:")
    assert identity["input_spec_checksum"].startswith("sha256:")
    # The prompt text is never part of the persisted identity.
    assert not any("Traditional Chinese" in value for value in identity.values())


def test_pc19d_canonical_model_retains_source_field_identity():
    canonical = build_canonical_prompt(spec(), PromptDialect.MINIMAX)
    fields = [fragment.source_field for fragment in canonical.fragments]
    assert "generation_spec.bpm" in fields
    assert "generation_spec.instruments" in fields
    assert "tone_profile.primary_tone" in fields
    assert all(fragment.text for fragment in canonical.fragments)
    assert canonical.payload()["model_version"] == CANONICAL_MUSIC_PROMPT_VERSION


def test_pc19e_input_spec_checksum_tracks_authoritative_changes():
    base = input_spec_checksum(spec())
    assert input_spec_checksum(spec(bpm=72)) != base
    assert input_spec_checksum(spec(instruments=["古琴"])) != base
    assert input_spec_checksum(spec(energy_curve="平稳专注")) != base
    assert input_spec_checksum(spec()) == base


# --------------------------------------------------------------------------- #
# PC20 / PC21 — vocabulary and neutrality guards
# --------------------------------------------------------------------------- #
def test_pc20_no_raw_internal_tone_enum_leaks_in_any_dialect_configuration():
    profiles = [
        _tone_profile(primary_tone=tone, secondary_tone=None) for tone in TONE_CODES
    ] + [
        _tone_profile(
            regulation_mode="integrated_regulation",
            primary_tone=None,
            secondary_tone=None,
            weights={tone: 0.2 for tone in TONE_CODES},
        )
    ]
    for profile in profiles:
        for dialect in ALL_DIALECTS:
            text = compile_music_prompt(
                spec(tone_profile=profile), dialect
            ).text
            for tone in TONE_CODES:
                assert not re.search(rf"\b{tone}\b", text, re.IGNORECASE), text


def test_pc20b_descriptor_table_is_versioned_and_complete():
    assert TONE_DESCRIPTOR_VERSION
    assert set(TONE_PROMPT_DESCRIPTORS) == set(TONE_CODES)
    for tone, descriptor in TONE_PROMPT_DESCRIPTORS.items():
        assert descriptor.strip()
        assert not re.search(rf"\b{tone}\b", descriptor, re.IGNORECASE)


def test_pc21_compiler_does_not_introduce_medical_language():
    compiled = compile_for(PromptDialect.TOKENHUB_MINIMAX)
    for pattern in (
        "diagnos",
        "syndrom",
        "disease",
        "severity",
        "treatment",
        "medication",
        "patient",
        "诊断",
        "证型",
        "治疗",
    ):
        assert pattern.lower() not in compiled.text.lower()


def test_pc21b_medical_language_from_the_rule_asset_fails_closed():
    with pytest.raises(MusicProviderFailureV3) as caught:
        compile_for(
            PromptDialect.MINIMAX, forbidden_constraints=["避免诊断为肝郁"]
        )
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert isinstance(caught.value.cause, PromptCompilerContractError)
    assert caught.value.cause.reason_code == "PROMPT_COMPILER_MEDICAL_LANGUAGE"


def test_pc21c_unknown_dialect_is_a_contract_error():
    with pytest.raises(MusicProviderFailureV3) as caught:
        compile_music_prompt(spec(), "not-a-dialect")  # type: ignore[arg-type]
    assert caught.value.error_code == "GENERATION_PROVIDER_REJECTED"
    assert caught.value.cause.reason_code == "PROMPT_COMPILER_DIALECT_UNKNOWN"


def test_pc21d_spec_is_not_mutated_by_compilation():
    authoritative = spec()
    before = authoritative.model_dump(mode="json")
    compile_music_prompt(authoritative, PromptDialect.STABILITY)
    assert authoritative.model_dump(mode="json") == before

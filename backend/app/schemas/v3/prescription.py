"""Frozen V3 contracts for Agent 3 and provider-neutral music specifications."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .common import (
    NonEmptyString,
    Score01,
    ToneCode,
    UserGoal,
    V3BaseModel,
)


class ToneBasis(V3BaseModel):
    diagnosis_id: NonEmptyString
    supporting_fact_ids: list[NonEmptyString]


class _WeightedToneProfile(V3BaseModel):
    schema_version: Literal["tone_profile_v3.0"]
    weights: dict[ToneCode, Score01]
    dominant_tone: ToneCode
    score_semantics: Literal["relative_tone_distribution"]
    mapping_version: NonEmptyString
    basis: ToneBasis

    @model_validator(mode="after")
    def validate_tone_weights(self) -> "_WeightedToneProfile":
        if set(self.weights) != set(ToneCode):
            raise ValueError("weighted tone profile requires all five tones")
        if abs(sum(self.weights.values()) - 1.0) > 0.001:
            raise ValueError("tone weights must sum to 1 ± 0.001")
        maximum = max(self.weights.values())
        if abs(self.weights[self.dominant_tone] - maximum) > 0.001:
            raise ValueError("dominant_tone must have a maximum weight")
        return self


class AvailableToneProfile(_WeightedToneProfile):
    status: Literal["available"]


class FallbackToneProfile(_WeightedToneProfile):
    status: Literal["fallback"]


class InsufficientToneProfile(V3BaseModel):
    schema_version: Literal["tone_profile_v3.0"]
    status: Literal["insufficient"]
    weights: None
    dominant_tone: None
    score_semantics: Literal["relative_tone_distribution"]
    mapping_version: NonEmptyString | None
    basis: ToneBasis | None


ToneProfile: TypeAlias = Annotated[
    AvailableToneProfile | FallbackToneProfile | InsufficientToneProfile,
    Field(discriminator="status"),
]


class WeightedPreference(V3BaseModel):
    code: NonEmptyString
    weight: Score01
    sample_count: Annotated[int, Field(ge=0)]


class PreferredBpmRange(V3BaseModel):
    min: Annotated[int, Field(ge=40, le=120)]
    max: Annotated[int, Field(ge=40, le=120)]
    weight: Score01

    @model_validator(mode="after")
    def validate_order(self) -> "PreferredBpmRange":
        if self.min > self.max:
            raise ValueError("preferred BPM min cannot exceed max")
        return self


class PreferredDuration(V3BaseModel):
    value: Annotated[int, Field(gt=0)]
    weight: Score01


class PreferenceSnapshot(V3BaseModel):
    profile_id: NonEmptyString
    version: Annotated[int, Field(ge=1)]
    preferred_instruments: list[WeightedPreference]
    disliked_instruments: list[WeightedPreference]
    preferred_bpm_range: PreferredBpmRange | None
    preferred_duration_seconds: PreferredDuration | None
    preferred_ambient: list[WeightedPreference]


class PrescriptionV3Request(V3BaseModel):
    schema_version: Literal["prescription_v3.0"]
    diagnosis_id: NonEmptyString
    user_goal: UserGoal
    preference_snapshot: PreferenceSnapshot | None


class PrescriptionV31Request(V3BaseModel):
    """Owner Flow prescription input.

    The optional UserGoal is captured on the Assessment as an independent
    personalization input. Prescription consumes that confirmed assessment
    value and never accepts a second request-level goal override.
    """

    schema_version: Literal["prescription_v3.1"]
    diagnosis_id: NonEmptyString
    preference_snapshot: PreferenceSnapshot | None = None


class GenerationStructure(V3BaseModel):
    intro_seconds: Annotated[int, Field(ge=0)]
    main_seconds: Annotated[int, Field(ge=0)]
    outro_seconds: Annotated[int, Field(ge=0)]


class GenerationFallbackPolicy(V3BaseModel):
    allow_local_matching: bool


class GenerationSpec(V3BaseModel):
    schema_version: Literal["generation_spec_v3.0"]
    tone_profile: ToneProfile
    bpm: Annotated[int, Field(ge=40, le=120)]
    duration_seconds: Annotated[int, Field(gt=0)]
    instruments: Annotated[list[NonEmptyString], Field(min_length=1)]
    ambient_sounds: list[NonEmptyString]
    structure: GenerationStructure
    energy_curve: NonEmptyString
    forbidden_constraints: list[NonEmptyString]
    fallback_policy: GenerationFallbackPolicy

    @model_validator(mode="after")
    def segments_must_equal_duration(self) -> "GenerationSpec":
        total = (
            self.structure.intro_seconds
            + self.structure.main_seconds
            + self.structure.outro_seconds
        )
        if total != self.duration_seconds:
            raise ValueError("generation structure must sum to duration_seconds")
        return self


PrescriptionMode = Literal[
    "syndrome_based",
    "candidate_blend",
    "emotion_based",
    "wellness",
]


class PreferenceProfileRef(V3BaseModel):
    profile_id: NonEmptyString
    version: Annotated[int, Field(ge=1)]


class PersonalizationAdjustment(V3BaseModel):
    field: NonEmptyString
    from_: str | None = Field(alias="from")
    to: str | None
    reason_code: NonEmptyString

    model_config = {"extra": "forbid", "populate_by_name": True}


class PrescriptionPersonalization(V3BaseModel):
    applied: bool
    profile_ref: PreferenceProfileRef | None
    adjustments: list[PersonalizationAdjustment]

    @model_validator(mode="after")
    def applied_requires_profile(self) -> "PrescriptionPersonalization":
        if self.applied and self.profile_ref is None:
            raise ValueError("applied personalization requires profile_ref")
        if not self.applied and self.adjustments:
            raise ValueError("non-applied personalization cannot contain adjustments")
        return self


class PrescriptionPresentation(V3BaseModel):
    title: NonEmptyString
    tone_summary: NonEmptyString
    parameter_summaries: list[NonEmptyString]
    personalization_summary: NonEmptyString


class PrescriptionV3(V3BaseModel):
    schema_version: Literal["prescription_v3.0"]
    agent_id: Literal["prescription_agent"]
    prescription_id: NonEmptyString
    diagnosis_id: NonEmptyString
    status: Literal["success", "degraded", "withheld", "failed"]
    prescription_mode: PrescriptionMode | None
    generation_spec: GenerationSpec | None
    personalization: PrescriptionPersonalization
    presentation: PrescriptionPresentation

    @model_validator(mode="after")
    def validate_authoritative_output(self) -> "PrescriptionV3":
        if self.status in {"success", "degraded"}:
            if self.prescription_mode is None or self.generation_spec is None:
                raise ValueError("successful prescription requires mode and generation_spec")
        elif self.prescription_mode is not None or self.generation_spec is not None:
            raise ValueError("withheld/failed prescription cannot contain generation_spec")
        return self

"""Frozen V3 contracts for Agent 5 feedback and preference learning."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .common import NonEmptyString, Score01, Timestamp, V3BaseModel
from .music import MusicRef


StateScore = Annotated[int, Field(ge=0, le=10)]
ChangeLabel = Literal["much_better", "slightly_better", "no_change", "worse"]
AdjustmentPreference = Literal[
    "slower_tempo",
    "faster_tempo",
    "change_instruments",
    "adjust_volume",
    "adjust_ambient",
    "shorter_duration",
    "longer_duration",
]


class PreStateSnapshot(V3BaseModel):
    snapshot_id: NonEmptyString
    source: Literal["player_session"]
    captured_at: Timestamp
    tension: StateScore | None = None
    fatigue: StateScore | None = None


class PostState(V3BaseModel):
    change_label: ChangeLabel
    tension: StateScore | None = None
    fatigue: StateScore | None = None


class FeedbackExperience(V3BaseModel):
    overall_rating: Annotated[int, Field(ge=1, le=5)] | None = None
    music_match_rating: Annotated[int, Field(ge=1, le=5)] | None = None


class PlaybackSummary(V3BaseModel):
    played_seconds: Annotated[int, Field(ge=0)]
    completed: bool


class FeedbackV3(V3BaseModel):
    schema_version: Literal["feedback_v3.0"]
    session_id: NonEmptyString
    music_ref: MusicRef
    pre_state_snapshot: PreStateSnapshot
    post_state: PostState
    experience: FeedbackExperience | None = None
    continue_use: Literal["yes", "maybe", "no"] | None = None
    favorite: bool | None = None
    liked_features: list[NonEmptyString] = Field(default_factory=list)
    adjustment_preferences: list[AdjustmentPreference] = Field(default_factory=list)
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None
    playback: PlaybackSummary | None = None

    @model_validator(mode="after")
    def validate_selection_sets(self) -> "FeedbackV3":
        if len(self.liked_features) != len(set(self.liked_features)):
            raise ValueError("liked_features cannot contain duplicates")
        selections = set(self.adjustment_preferences)
        if len(selections) != len(self.adjustment_preferences):
            raise ValueError("adjustment_preferences cannot contain duplicates")
        for left, right in (
            ("slower_tempo", "faster_tempo"),
            ("shorter_duration", "longer_duration"),
        ):
            if left in selections and right in selections:
                raise ValueError(f"conflicting adjustment preferences: {left}/{right}")
        return self


class WeightedPreference(V3BaseModel):
    code: NonEmptyString
    weight: Score01
    sample_count: Annotated[int, Field(ge=0)]
    updated_at: Timestamp


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


class PreferenceLearning(V3BaseModel):
    feedback_count: Annotated[int, Field(ge=0)]
    minimum_samples_for_application: Annotated[int, Field(ge=1)]


class UserPreferenceProfile(V3BaseModel):
    schema_version: Literal["user_music_preference_v3.0"]
    profile_id: NonEmptyString
    public_user_id: NonEmptyString
    version: Annotated[int, Field(ge=1)]
    preferred_instruments: list[WeightedPreference]
    disliked_instruments: list[WeightedPreference]
    preferred_features: list[WeightedPreference]
    disliked_features: list[WeightedPreference]
    preferred_ambient: list[WeightedPreference]
    preferred_bpm_range: PreferredBpmRange | None
    preferred_duration_seconds: PreferredDuration | None
    favorite_music_refs: list[MusicRef]
    learning: PreferenceLearning


class PreferenceUpdate(V3BaseModel):
    applied: bool
    previous_version: Annotated[int, Field(ge=1)] | None
    new_version: Annotated[int, Field(ge=1)] | None
    changed_fields: list[NonEmptyString]

    @model_validator(mode="after")
    def validate_version_transition(self) -> "PreferenceUpdate":
        if self.applied:
            if self.previous_version is None or self.new_version != self.previous_version + 1:
                raise ValueError("applied preference update must advance exactly one version")
        elif self.new_version is not None or self.changed_fields:
            raise ValueError("non-applied preference update cannot claim changes")
        return self


class FeedbackPresentation(V3BaseModel):
    message: NonEmptyString


class FeedbackV3Output(V3BaseModel):
    feedback_id: NonEmptyString
    status: Literal["saved"]
    preference_update: PreferenceUpdate
    presentation: FeedbackPresentation

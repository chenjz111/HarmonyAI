from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
)


class PreState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tension: StrictInt | None = Field(default=None, ge=0, le=10)
    body_tension: StrictInt | None = Field(default=None, ge=0, le=10)
    mental_fatigue: StrictInt | None = Field(default=None, ge=0, le=10)
    goal: str | None = Field(default=None, min_length=1)


class PostState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tension: StrictInt | None = Field(default=None, ge=0, le=10)
    body_tension: StrictInt | None = Field(default=None, ge=0, le=10)
    mental_fatigue: StrictInt | None = Field(default=None, ge=0, le=10)
    change_label: Literal[
        "much_better",
        "slightly_better",
        "no_change",
        "worse",
    ]


class FeedbackExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_rating: StrictInt | None = Field(default=None, ge=1, le=5)
    relaxation_rating: StrictInt | None = Field(default=None, ge=1, le=5)
    music_match_rating: StrictInt | None = Field(default=None, ge=1, le=5)
    continue_use: Literal["yes", "maybe", "no"] | None = None
    favorite: StrictBool | None = None
    disliked_features: list[str] = Field(default_factory=list)
    disliked_instruments: list[str] = Field(default_factory=list)
    liked_features: list[str] = Field(default_factory=list)
    adjustment_preferences: list[str] = Field(default_factory=list)
    comment: str = Field(default="", max_length=500)

    @field_validator(
        "disliked_features",
        "disliked_instruments",
        "liked_features",
        "adjustment_preferences",
        mode="after",
    )
    @classmethod
    def normalize_string_list(cls, value: list[str]) -> list[str]:
        return list(
            dict.fromkeys(item.strip() for item in value if item.strip())
        )

    @field_validator("comment", mode="after")
    @classmethod
    def normalize_comment(cls, value: str) -> str:
        return value.strip()


class PlaybackSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listened_seconds: StrictInt = Field(ge=0)
    duration_seconds: StrictInt = Field(gt=0)
    completion_rate: StrictFloat = Field(ge=0, le=1)
    pause_count: StrictInt = Field(default=0, ge=0)
    skip_count: StrictInt = Field(default=0, ge=0)


class FeedbackV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["feedback_v2.0"]
    session_id: str = Field(min_length=1)
    prescription_id: str = Field(min_length=1)
    music_id: str = Field(min_length=1)
    pre_state: PreState = Field(default_factory=PreState)
    post_state: PostState
    experience: FeedbackExperience = Field(default_factory=FeedbackExperience)
    playback: PlaybackSummary | None = None
    submitted_at: datetime | None = None


class SubjectiveChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tension_delta: int | None
    body_tension_delta: int | None
    mental_fatigue_delta: int | None
    summary: str = Field(min_length=1)


class ExperienceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_rating: int | None
    relaxation_rating: int | None
    music_match_rating: int | None
    continue_use: Literal["yes", "maybe", "no"] | None
    favorite: bool | None


class FeedbackDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "adjust_personal_preference",
        "keep_personal_preference",
        "reduce_current_music",
    ]
    reason_codes: list[str]


class PersonalPreferencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reduce_instruments: list[str]
    reduce_high_frequency: bool
    preserve_instruments: list[str]
    favorite_tracks_add: list[str]
    preferred_features: list[str]
    adjustment_preferences: list[str]


class FeedbackV2Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str = Field(min_length=1)
    agent_id: Literal["feedback_agent"]
    status: Literal["success"]
    idempotent: bool
    subjective_change: SubjectiveChange
    experience_summary: ExperienceSummary
    decision: FeedbackDecision
    personal_preference_patch: PersonalPreferencePatch
    global_rule_update: Literal[False]
    warnings: list[str]

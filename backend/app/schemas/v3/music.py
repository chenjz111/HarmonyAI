"""Frozen V3 contracts for Agent 4 and music generation providers."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

from .common import NonEmptyString, Score01, V3BaseModel
from .prescription import GenerationSpec, ToneProfile


class MusicProviderPolicy(V3BaseModel):
    mode: Literal["prefer_real_generation"]
    fallback: Literal["local_matching", "none"]


class MusicProviderCapabilities(V3BaseModel):
    max_duration_seconds: Annotated[int, Field(gt=0)]
    supports_progress: bool
    supports_cancel: bool
    supported_instruments: Annotated[list[NonEmptyString], Field(min_length=1)]
    supported_formats: Annotated[
        list[Literal["mp3", "wav", "m4a"]],
        Field(min_length=1),
    ]


class MusicGenerationV3Request(V3BaseModel):
    schema_version: Literal["music_generation_v3.0"]
    request_id: NonEmptyString
    prescription_id: NonEmptyString
    idempotency_key: Annotated[str, Field(pattern=r"^sha256:.+")]
    generation_spec: GenerationSpec
    provider_policy: MusicProviderPolicy


class ProviderMusicRequest(V3BaseModel):
    provider_request_id: NonEmptyString
    generation_spec: GenerationSpec
    output_format: Literal["mp3", "wav", "m4a"]
    callback_ref: NonEmptyString | None


class ProviderTask(V3BaseModel):
    provider_task_id: NonEmptyString
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress_value: Annotated[int, Field(ge=0, le=100)] | None
    asset_locator: NonEmptyString | None
    error_code: NonEmptyString | None

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "ProviderTask":
        if self.status == "succeeded" and self.asset_locator is None:
            raise ValueError("succeeded provider task requires asset_locator")
        if self.status == "failed" and self.error_code is None:
            raise ValueError("failed provider task requires stable error_code")
        if self.status in {"queued", "running", "cancelled"} and self.asset_locator:
            raise ValueError("non-success provider task cannot contain asset_locator")
        return self


class MusicRef(V3BaseModel):
    music_id: NonEmptyString
    source_type: Literal["generated", "matched", "comfort_audio"]


class AudioAsset(V3BaseModel):
    music_ref: MusicRef
    title: NonEmptyString
    stream_url: Annotated[str, Field(pattern=r"^/api/v3/music/assets/.+/stream$")]
    duration_seconds: Annotated[int, Field(gt=0)]
    format: Literal["mp3", "wav", "m4a"]
    checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    tone_profile: ToneProfile
    bpm: Annotated[int, Field(ge=40, le=120)]
    instruments: Annotated[list[NonEmptyString], Field(min_length=1)]


class MusicProgress(V3BaseModel):
    value: Annotated[int, Field(ge=0, le=100)] | None
    semantics: NonEmptyString
    indeterminate: bool

    @model_validator(mode="after")
    def validate_progress_shape(self) -> "MusicProgress":
        if self.indeterminate and self.value is not None:
            raise ValueError("indeterminate progress cannot claim a value")
        if not self.indeterminate and self.value is None:
            raise ValueError("determinate progress requires value")
        return self


class MusicFallback(V3BaseModel):
    applied: bool
    reason_code: NonEmptyString | None

    @model_validator(mode="after")
    def applied_fallback_requires_reason(self) -> "MusicFallback":
        if self.applied and self.reason_code is None:
            raise ValueError("applied fallback requires reason_code")
        if not self.applied and self.reason_code is not None:
            raise ValueError("non-applied fallback cannot contain reason_code")
        return self


class _MusicTaskBase(V3BaseModel):
    task_id: NonEmptyString
    message: NonEmptyString
    fallback: MusicFallback


class QueuedMusicTask(_MusicTaskBase):
    status: Literal["queued"]
    progress: MusicProgress | None
    poll_after_ms: Annotated[int, Field(gt=0)] | None
    audio_asset: None
    error_code: None


class RunningMusicTask(_MusicTaskBase):
    status: Literal["running"]
    progress: MusicProgress | None
    poll_after_ms: Annotated[int, Field(gt=0)]
    audio_asset: None
    error_code: None


class SucceededMusicTask(_MusicTaskBase):
    status: Literal["succeeded"]
    progress: MusicProgress
    poll_after_ms: None
    audio_asset: AudioAsset
    error_code: None

    @model_validator(mode="after")
    def validate_success_asset(self) -> "SucceededMusicTask":
        if self.progress.indeterminate or self.progress.value != 100:
            raise ValueError("succeeded task requires 100 percent progress")
        if self.audio_asset.music_ref.source_type != "generated":
            raise ValueError("succeeded task requires generated asset")
        if self.fallback.applied:
            raise ValueError("succeeded generation cannot be marked as fallback")
        return self


class MatchedFallbackMusicTask(_MusicTaskBase):
    status: Literal["matched_fallback"]
    progress: MusicProgress
    poll_after_ms: None
    audio_asset: AudioAsset
    error_code: None

    @model_validator(mode="after")
    def validate_fallback_asset(self) -> "MatchedFallbackMusicTask":
        if self.progress.indeterminate or self.progress.value != 100:
            raise ValueError("matched fallback requires 100 percent progress")
        if self.audio_asset.music_ref.source_type != "matched":
            raise ValueError("matched fallback requires matched asset")
        if not self.fallback.applied:
            raise ValueError("matched fallback must record fallback reason")
        return self


class FailedMusicTask(_MusicTaskBase):
    status: Literal["failed"]
    progress: None
    poll_after_ms: None
    audio_asset: None
    error_code: NonEmptyString


class CancelledMusicTask(_MusicTaskBase):
    status: Literal["cancelled"]
    progress: None
    poll_after_ms: None
    audio_asset: None
    error_code: None


MusicTask: TypeAlias = Annotated[
    QueuedMusicTask
    | RunningMusicTask
    | SucceededMusicTask
    | MatchedFallbackMusicTask
    | FailedMusicTask
    | CancelledMusicTask,
    Field(discriminator="status"),
]

"""Frozen V3 contracts for source understanding and revision confirmation."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue, StringConstraints, model_validator

from .common import (
    Degradation,
    NonEmptyString,
    NormalizedFactValue,
    SafetyStatus,
    Score01,
    SourceRef,
    SourceType,
    Timestamp,
    V3BaseModel,
)


SourceProcessingStatus = Literal[
    "uploading",
    "processing",
    "needs_confirmation",
    "ready",
    "degraded",
    "failed",
    "skipped",
]
UnderstandingStatus = Literal[
    "queued",
    "processing",
    "needs_confirmation",
    "confirmed",
    "degraded",
    "failed",
]


class UnderstandingSource(V3BaseModel):
    source_id: NonEmptyString
    source_type: SourceType
    processing_status: SourceProcessingStatus
    text_ref: NonEmptyString | None = None
    text: NonEmptyString | None = None
    captured_at: Timestamp

    @model_validator(mode="after")
    def require_one_text_source(self) -> "UnderstandingSource":
        if (self.text_ref is None) == (self.text is None):
            raise ValueError("exactly one of text_ref or text is required")
        return self


class UnderstandingV3Request(V3BaseModel):
    schema_version: Literal["understanding_v3.0"]
    session_id: NonEmptyString
    inputs: Annotated[list[UnderstandingSource], Field(min_length=1)]


class UnderstandingV31Request(V3BaseModel):
    """Owner Flow Amendment 001 §4.2 — new flow run discriminator.

    New clients must use ``understanding_v3.1``; the v3.0 shape is kept for
    legacy compatibility and is never auto-migrated. The server validates
    every document source against the session's active input before any
    Provider/Agent work.
    """

    schema_version: Literal["understanding_v3.1"]
    session_id: NonEmptyString
    expected_input_revision: Annotated[int, Field(ge=1)]
    inputs: Annotated[list[UnderstandingSource], Field(min_length=1)]


class TextSpan(V3BaseModel):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "TextSpan":
        if self.end <= self.start:
            raise ValueError("span end must be greater than start")
        return self


class ProviderSource(V3BaseModel):
    source_id: NonEmptyString
    source_type: SourceType
    subject_hint: Literal["self", "other", "unknown"]
    time_window: NonEmptyString
    text: NonEmptyString


class UnderstandingProviderRequest(V3BaseModel):
    request_id: NonEmptyString
    schema_version: Literal["understanding_provider_v3.0"]
    prompt_version: NonEmptyString
    source: ProviderSource
    allowed_claim_dictionary_version: NonEmptyString
    max_facts: Annotated[int, Field(ge=1, le=30)]


class UnderstandingProviderFact(V3BaseModel):
    claim_code: NonEmptyString
    display_name: NonEmptyString
    category: NonEmptyString
    value: NormalizedFactValue
    time_window: NonEmptyString
    negated: bool
    subject: Literal["self", "other", "unknown"]
    span: TextSpan
    extraction_confidence: Score01


class UnderstandingProviderResponse(V3BaseModel):
    status: Literal["success", "degraded", "failed"]
    facts: list[UnderstandingProviderFact]
    warnings: list[NonEmptyString]

    @model_validator(mode="after")
    def failed_response_has_no_facts(self) -> "UnderstandingProviderResponse":
        if self.status == "failed" and self.facts:
            raise ValueError("failed provider response cannot contain facts")
        return self


class EditableField(V3BaseModel):
    field_id: NonEmptyString
    label: NonEmptyString
    value: str
    value_type: Literal["text"]
    required: bool


class CaseSummary(V3BaseModel):
    case_summary_id: NonEmptyString
    source_document_ids: Annotated[list[NonEmptyString], Field(min_length=1)]
    revision: Annotated[int, Field(ge=1)]
    status: Literal["needs_confirmation", "confirmed", "rejected", "failed"]
    title: NonEmptyString
    summary: str
    editable_fields: list[EditableField]
    warnings: list[NonEmptyString]


class VoiceTranscriptSegment(V3BaseModel):
    segment_id: NonEmptyString
    start_ms: Annotated[int, Field(ge=0)]
    end_ms: Annotated[int, Field(gt=0)]
    text: NonEmptyString

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "VoiceTranscriptSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("segment end must be greater than start")
        return self


class VoiceTranscript(V3BaseModel):
    transcript_id: NonEmptyString
    audio_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]
    status: Literal["needs_confirmation", "confirmed", "failed"]
    language: NonEmptyString
    text: str
    segments: list[VoiceTranscriptSegment]
    degradation: Degradation

    @model_validator(mode="after")
    def successful_transcript_is_not_empty(self) -> "VoiceTranscript":
        if self.status != "failed" and not self.text.strip():
            raise ValueError("non-failed transcript requires text")
        return self


class FactExtraction(V3BaseModel):
    method: Literal[
        "qwen",
        "rule",
        "user_correction",
        "deterministic_questionnaire_mapping",
    ]
    confidence: Score01 | None = None


class NormalizedFact(V3BaseModel):
    fact_id: NonEmptyString
    fact_code: NonEmptyString
    display_name: NonEmptyString
    category: NonEmptyString
    value: NormalizedFactValue
    time_window: NonEmptyString
    negated: bool
    subject: Literal["self", "other", "unknown"]
    source_refs: Annotated[list[SourceRef], Field(min_length=1)]
    confirmation_status: Literal["confirmed", "unconfirmed", "rejected"]
    extraction: FactExtraction


class FactOwnerRef(V3BaseModel):
    owner_type: Literal["understanding", "questionnaire"]
    understanding_id: NonEmptyString | None = None
    understanding_revision: Annotated[int, Field(ge=1)] | None = None
    questionnaire_submission_id: NonEmptyString | None = None

    @model_validator(mode="after")
    def enforce_owner_xor(self) -> "FactOwnerRef":
        if self.owner_type == "understanding":
            if (
                self.understanding_id is None
                or self.understanding_revision is None
                or self.questionnaire_submission_id is not None
            ):
                raise ValueError("understanding owner requires only understanding id/revision")
        elif (
            self.questionnaire_submission_id is None
            or self.understanding_id is not None
            or self.understanding_revision is not None
        ):
            raise ValueError("questionnaire owner requires only questionnaire_submission_id")
        return self


class SourceStatus(V3BaseModel):
    source_id: NonEmptyString
    source_type: SourceType
    status: SourceProcessingStatus


class UnderstandingV3Response(V3BaseModel):
    schema_version: Literal["understanding_v3.0"]
    understanding_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]
    status: UnderstandingStatus
    case_summary: CaseSummary | None
    voice_transcripts: list[VoiceTranscript]
    normalized_facts: list[NormalizedFact]
    source_statuses: list[SourceStatus]
    safety_status: SafetyStatus
    safety_signal_refs: list[NonEmptyString]
    degradation: Degradation


class UnderstandingV31Response(UnderstandingV3Response):
    """Owner Flow Amendment 001 §6 — new flow discriminator with deferred Safety.

    `safety_status` is always null under `deferred_v3`: the pipeline is
    deliberately not run, and the system must not claim a risk verdict.
    """

    schema_version: Literal["understanding_v3.1"]
    flow_contract_version: Literal["v3-owner-flow-1"]
    safety_policy: Literal["deferred_v3"]
    safety_evaluation_status: Literal["not_run"]
    safety_status: None


class RevisionChange(V3BaseModel):
    target_type: Literal["normalized_fact", "case_summary", "voice_transcript", "source"]
    target_id: NonEmptyString
    field: NonEmptyString
    old_value: JsonValue
    new_value: JsonValue
    reason: NonEmptyString | None = None


class UnderstandingConfirmationRequest(V3BaseModel):
    expected_revision: Annotated[int, Field(ge=1)]
    decision: Literal["confirm", "confirm_with_changes", "reject_source", "cannot_confirm"]
    changes: list[RevisionChange] = Field(default_factory=list)
    reprocess_requested: bool = False

    @model_validator(mode="after")
    def validate_decision_changes(self) -> "UnderstandingConfirmationRequest":
        if self.decision == "confirm_with_changes" and not self.changes:
            raise ValueError("confirm_with_changes requires at least one change")
        if self.decision != "confirm_with_changes" and self.changes:
            raise ValueError("changes are only allowed for confirm_with_changes")
        return self


EditedSummaryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class UnderstandingV31ConfirmationRequest(V3BaseModel):
    """Owner Flow Amendment 001 §4.2 — new-flow confirmation discriminator.

    `reject_source` / `cannot_confirm` are not valid here: discarding or
    re-uploading a source goes through `input-transitions` instead, and the
    legacy decisions keep their old behavior on `understanding_v3.0`.
    """

    schema_version: Literal["understanding_v3.1"]
    expected_revision: Annotated[int, Field(ge=1)]
    expected_input_revision: Annotated[int, Field(ge=1)]
    decision: Literal["confirm", "confirm_with_changes"]
    changes: list[RevisionChange] = Field(default_factory=list)
    edited_summary_text: EditedSummaryText | None = None
    reprocess_requested: bool = False

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "UnderstandingV31ConfirmationRequest":
        if self.decision == "confirm":
            if self.changes or self.edited_summary_text is not None or self.reprocess_requested:
                raise ValueError(
                    "confirm cannot carry changes, edited_summary_text, or reprocess_requested"
                )
            return self
        full_edit = self.edited_summary_text is not None
        structured = bool(self.changes)
        if full_edit == structured:
            raise ValueError(
                "confirm_with_changes requires either edited_summary_text with "
                "reprocess_requested or structured changes, not both"
            )
        if full_edit and not self.reprocess_requested:
            raise ValueError("full-text edit requires reprocess_requested=true")
        if structured and self.reprocess_requested:
            raise ValueError("structured changes cannot request reprocessing")
        return self


class UnderstandingRevisionResult(V3BaseModel):
    understanding_id: NonEmptyString
    previous_revision: Annotated[int, Field(ge=1)]
    revision: Annotated[int, Field(ge=2)]
    status: Literal["confirmed", "needs_confirmation", "rejected"]
    applied_changes: list[NonEmptyString]
    affected_fact_ids: list[NonEmptyString]

    @model_validator(mode="after")
    def revision_must_advance_once(self) -> "UnderstandingRevisionResult":
        if self.revision != self.previous_revision + 1:
            raise ValueError("revision must advance exactly once")
        return self


class SafetySignalResolution(V3BaseModel):
    safety_signal_ref: NonEmptyString
    resolution: Literal[
        "current_self",
        "past_resolved",
        "other_person",
        "recognition_error",
        "cannot_confirm",
    ]


class SafetyResolutionRequest(V3BaseModel):
    expected_revision: Annotated[int, Field(ge=1)]
    resolutions: Annotated[list[SafetySignalResolution], Field(min_length=1)]


class AsrTask(V3BaseModel):
    task_id: NonEmptyString
    status: Literal["queued", "running", "succeeded", "failed"]
    transcript: VoiceTranscript | None = None
    error_code: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "AsrTask":
        if self.status == "succeeded" and self.transcript is None:
            raise ValueError("succeeded ASR task requires transcript")
        if self.status == "failed" and self.error_code is None:
            raise ValueError("failed ASR task requires stable error_code")
        if self.status in {"queued", "running"} and (self.transcript or self.error_code):
            raise ValueError("non-terminal ASR task cannot contain terminal payload")
        return self

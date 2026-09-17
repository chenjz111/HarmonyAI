"""Executable freeze-candidate contracts for the HarmonyAI V3.1 user flow.

These transport models freeze cross-layer shape, validation, authority, and
revision binding. They do not prescribe ORM/table names or provider details.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StringConstraints, model_validator

from .common import (
    NonEmptyString,
    QuestionnaireAnswer,
    Score01,
    Timestamp,
    ToneCode,
    UserGoalCode,
    V3BaseModel,
)

Checksum = Annotated[str, Field(pattern=r"^sha256:.+")]
PositiveRevision = Annotated[int, Field(ge=1)]
PublicText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Sprint 6 frozen music-design modes (backend authority).
#
#   personalized_five_tone : evidence sufficient + a genuine dominant direction
#   integrated_regulation  : evidence sufficient, no single dominant direction
#   basic_wellness         : evidence insufficient / legal abstain
#
# ``integrated_regulation`` and ``basic_wellness`` never carry a primary tone
# (均衡 ≠ 宫 / 证据不足 ≠ 宫 / abstain ≠ 宫). Technical failures are NOT modes.
RegulationMode = Literal[
    "personalized_five_tone",
    "integrated_regulation",
    "basic_wellness",
]

# Phase 1A mode-contract version signal.
#
# Phase 1A changed the mode-bearing payload shape (added ``regulation_mode``,
# made ``primary_tone``/``weights`` mode-scoped). The schema version therefore
# distinguishes new mode-bearing payloads from pre-Phase-1A rows **without
# inspecting ``primary_tone``**. Pre-1A rows keep their historical version and
# are handled only by the row-aware compatibility resolver
# (``backend.app.services.v3.legacy_mode_compat``); schema validators never
# invent a mode.
TONE_PROFILE_SCHEMA_VERSION = "tone_profile_v3.2"
FIVE_TONE_ANALYSIS_SCHEMA_VERSION = "five_tone_analysis_read_model_v3.2"
LEGACY_TONE_PROFILE_SCHEMA_VERSION = "tone_profile_v3.1"
LEGACY_FIVE_TONE_ANALYSIS_SCHEMA_VERSION = "five_tone_analysis_read_model_v3.1"

# Shared tolerance for weight *validation* only (weights sum to 1; a
# ``basic_wellness`` distribution must be neutral). It is deliberately NOT used
# for mode routing: the Phase 1A tie rule compares canonical normalised weights
# with exact equality, and any margin-based ambiguity rule belongs to Phase 1B.
MODE_WEIGHTS_TOLERANCE = 0.001

QUESTIONNAIRE_SCHEMA_ID = "questionnaire_v3"
QUESTIONNAIRE_SCHEMA_VERSION = "3.0.1"
QUESTIONNAIRE_MANIFEST_VERSION = "medical_v3.0.1"
QUESTIONNAIRE_CONTENT_CHECKSUM = (
    "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031"
)


class DocumentSetItem(V3BaseModel):
    document_id: NonEmptyString
    position: Annotated[int, Field(ge=1, le=3)]
    content_checksum: Checksum


class DocumentSet(V3BaseModel):
    schema_version: Literal["document_set_v3.1"]
    document_set_id: NonEmptyString
    session_id: NonEmptyString
    revision: PositiveRevision
    session_input_revision: PositiveRevision
    authority_status: Literal["current", "superseded", "discarded"]
    documents: Annotated[list[DocumentSetItem], Field(min_length=1, max_length=3)]

    @model_validator(mode="after")
    def validate_ordered_unique_documents(self) -> "DocumentSet":
        ids = [item.document_id for item in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document references must be unique")
        if [item.position for item in self.documents] != list(
            range(1, len(self.documents) + 1)
        ):
            raise ValueError("documents must be ordered with consecutive positions")
        return self


class DocumentSetRef(V3BaseModel):
    document_set_id: NonEmptyString
    revision: PositiveRevision


class RelevanceOutcome(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    IRRELEVANT = "IRRELEVANT"
    INSUFFICIENT = "INSUFFICIENT"


class DocumentRelevanceResult(V3BaseModel):
    schema_version: Literal["document_relevance_result_v3.1"]
    relevance_result_id: NonEmptyString
    run_id: NonEmptyString
    revision: PositiveRevision
    document_set_ref: DocumentSetRef
    outcome: RelevanceOutcome
    reason_code: NonEmptyString
    reason: PublicText
    may_enter_summary: bool
    may_form_evidence: bool
    may_enter_agent2: bool
    completed_at: Timestamp

    @model_validator(mode="after")
    def validate_downstream_gate(self) -> "DocumentRelevanceResult":
        expected = self.outcome is RelevanceOutcome.VALID
        if any(
            value is not expected
            for value in (
                self.may_enter_summary,
                self.may_form_evidence,
                self.may_enter_agent2,
            )
        ):
            raise ValueError(
                "only VALID relevance may enter summary, evidence, and Agent2"
            )
        return self


class RelevanceResultRef(V3BaseModel):
    relevance_result_id: NonEmptyString
    revision: PositiveRevision
    outcome: Literal[RelevanceOutcome.VALID]


class AiSummaryRef(V3BaseModel):
    summary_id: NonEmptyString
    revision: PositiveRevision


class OcrSourceRef(V3BaseModel):
    document_id: NonEmptyString
    ocr_result_id: NonEmptyString
    revision: PositiveRevision


class FinalConfirmedSummary(V3BaseModel):
    schema_version: Literal["final_confirmed_summary_v3.1"]
    summary_id: NonEmptyString
    session_id: NonEmptyString
    source_document_set_ref: DocumentSetRef
    source_relevance_result_ref: RelevanceResultRef
    source_ai_summary_ref: AiSummaryRef
    ocr_source_refs: Annotated[list[OcrSourceRef], Field(min_length=1, max_length=3)]
    confirmed_text: PublicText
    revision: PositiveRevision
    content_checksum: Checksum
    authority_status: Literal["current", "superseded"]
    confirmation_authority: Literal["user"]
    confirmed_at: Timestamp

    @model_validator(mode="after")
    def validate_ocr_sources(self) -> "FinalConfirmedSummary":
        ids = [item.document_id for item in self.ocr_source_refs]
        if len(ids) != len(set(ids)):
            raise ValueError("OCR source document references must be unique")
        return self


class QuestionnaireResult(V3BaseModel):
    schema_version: Literal["questionnaire_result_v3.1"]
    questionnaire_result_id: NonEmptyString
    session_id: NonEmptyString
    revision: PositiveRevision
    authority_status: Literal["current", "superseded"]
    input_mode: Literal["with_document", "without_document"]
    entry_requirement: Literal["optional", "required"]
    schema_id: Literal[QUESTIONNAIRE_SCHEMA_ID]
    questionnaire_schema_version: Literal[QUESTIONNAIRE_SCHEMA_VERSION]
    manifest_version: Literal[QUESTIONNAIRE_MANIFEST_VERSION]
    content_checksum: Literal[QUESTIONNAIRE_CONTENT_CHECKSUM]
    answers: Annotated[list[QuestionnaireAnswer], Field(min_length=10, max_length=10)]
    started_at: Timestamp
    completed_at: Timestamp

    @model_validator(mode="after")
    def validate_complete_authoritative_submission(self) -> "QuestionnaireResult":
        expected_ids = [f"q{index:02d}" for index in range(1, 11)]
        if [answer.question_id for answer in self.answers] != expected_ids:
            raise ValueError("answers must be a complete ordered q01-q10 submission")
        expected_requirement = (
            "required" if self.input_mode == "without_document" else "optional"
        )
        if self.entry_requirement != expected_requirement:
            raise ValueError("questionnaire requirement must match authoritative input_mode")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self


class UserGoalV31(V3BaseModel):
    """Optional music preference; a skipped or empty step is canonically ``None``."""

    primary_goal: UserGoalCode | None = None
    secondary_goal: UserGoalCode | None = None
    custom_goal_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ] | None = None

    @model_validator(mode="after")
    def validate_goal_combination(self) -> "UserGoalV31":
        if self.secondary_goal is not None and self.primary_goal is None:
            raise ValueError("secondary_goal requires primary_goal")
        if self.secondary_goal is not None and self.secondary_goal == self.primary_goal:
            raise ValueError("secondary_goal must differ from primary_goal")
        return self


def _empty_user_goal_to_none(value: object) -> object:
    if isinstance(value, dict):
        custom_text = value.get("custom_goal_text")
        if (
            value.get("primary_goal") is None
            and value.get("secondary_goal") is None
            and (
                custom_text is None
                or (isinstance(custom_text, str) and not custom_text.strip())
            )
        ):
            return None
    return value


UserGoalSubmissionV31 = Annotated[
    UserGoalV31 | None, BeforeValidator(_empty_user_goal_to_none)
]

class FinalConfirmedSummaryRef(V3BaseModel):
    summary_id: NonEmptyString
    revision: PositiveRevision
    content_checksum: Checksum
    confirmation_status: Literal["confirmed"]


class QuestionnaireResultRef(V3BaseModel):
    questionnaire_result_id: NonEmptyString
    revision: PositiveRevision
    content_checksum: Literal[QUESTIONNAIRE_CONTENT_CHECKSUM]
    completion_status: Literal["complete"]


class UserGoalRef(V3BaseModel):
    user_goal_id: NonEmptyString
    revision: PositiveRevision


class ConfirmedStateFact(V3BaseModel):
    fact_id: NonEmptyString
    claim_code: NonEmptyString
    display_text: PublicText
    source_refs: Annotated[list[NonEmptyString], Field(min_length=1)]


class ConfirmedUserState(V3BaseModel):
    """INTERNAL CONTRACT OBJECT, not a user-facing page.

    document_only inherits user confirmation from FinalConfirmedSummary.
    It does not require a second user confirmation. For questionnaire paths,
    confirmation authority comes from the recent state summary confirmation.
    """

    schema_version: Literal["confirmed_user_state_v3.1"]
    confirmed_user_state_id: NonEmptyString
    session_id: NonEmptyString
    source_mode: Literal[
        "document_only", "document_plus_questionnaire", "questionnaire_only"
    ]
    final_confirmed_summary_ref: FinalConfirmedSummaryRef | None
    questionnaire_result_ref: QuestionnaireResultRef | None
    user_goal_ref: UserGoalRef | None
    confirmed_state_text: PublicText
    normalized_projection: list[ConfirmedStateFact]
    revision: PositiveRevision
    content_checksum: Checksum
    authority_status: Literal["current"]
    confirmation_status: Literal["confirmed"]
    confirmed_by: Literal["user"]
    session_input_revision: PositiveRevision
    created_at: Timestamp

    @model_validator(mode="after")
    def validate_source_union(self) -> "ConfirmedUserState":
        expected = {
            "document_only": (True, False),
            "document_plus_questionnaire": (True, True),
            "questionnaire_only": (False, True),
        }[self.source_mode]
        actual = (
            self.final_confirmed_summary_ref is not None,
            self.questionnaire_result_ref is not None,
        )
        if actual != expected:
            raise ValueError("source references do not match source_mode")
        return self


class ConfirmedUserStateRef(V3BaseModel):
    confirmed_user_state_id: NonEmptyString
    revision: PositiveRevision
    content_checksum: Checksum


class ToneProfileBasisV31(V3BaseModel):
    diagnosis_id: NonEmptyString
    diagnosis_revision: PositiveRevision
    supporting_evidence_refs: list[NonEmptyString]


class ToneProfileV31(V3BaseModel):
    """Backend-authoritative tone profile for the frozen three-mode contract.

    ``regulation_mode`` is the authority: clients must never infer the mode from
    ``primary_tone == null``. Mode-scoped rules:

    * ``personalized_five_tone``: a primary tone is required and must carry the
      maximum weight; full five-tone weights are retained.
    * ``integrated_regulation``: ``primary_tone`` is null while the full
      five-tone weights are retained (balanced distribution, no dominant tone).
    * ``basic_wellness``: ``primary_tone`` is null; weights are absent or a
      neutral (uniform) distribution — no tone conclusion is fabricated.

    Sprint 5 rows persisted under ``tone_profile_v3.1`` have no
    ``regulation_mode`` and must never be reinterpreted here: this model only
    validates an explicit, already-resolved mode. Legacy classification belongs
    to the row-aware compatibility resolver, which has the diagnosis /
    prescription / checksum context needed to decide between
    ``personalized_five_tone``, ``basic_wellness`` and an explicit
    ``legacy-unclassified`` compatibility state.
    """

    schema_version: Literal["tone_profile_v3.2"]
    regulation_mode: RegulationMode
    weights: dict[ToneCode, Score01] | None = None
    primary_tone: ToneCode | None = None
    secondary_tone: ToneCode | None = None
    score_semantics: Literal["relative_tone_distribution"]
    mapping_version: NonEmptyString
    basis: ToneProfileBasisV31

    @model_validator(mode="after")
    def validate_tone_profile(self) -> "ToneProfileV31":
        if self.weights is not None:
            if set(self.weights) != set(ToneCode):
                raise ValueError("tone profile requires all five tone weights")
            if abs(sum(self.weights.values()) - 1.0) > MODE_WEIGHTS_TOLERANCE:
                raise ValueError("tone weights must sum to 1 ± 0.001")
        mode = self.regulation_mode
        if mode == "personalized_five_tone":
            if self.weights is None:
                raise ValueError("personalized_five_tone requires tone weights")
            if self.primary_tone is None:
                raise ValueError("personalized_five_tone requires a primary tone")
            maximum = max(self.weights.values())
            if abs(self.weights[self.primary_tone] - maximum) > MODE_WEIGHTS_TOLERANCE:
                raise ValueError("primary_tone must have a maximum weight")
            if self.secondary_tone == self.primary_tone:
                raise ValueError("secondary_tone must differ from primary_tone")
            return self
        # integrated_regulation / basic_wellness: no primary tone may be claimed
        if self.primary_tone is not None:
            raise ValueError(f"{mode} must not carry a primary tone")
        if self.secondary_tone is not None:
            raise ValueError(f"{mode} must not carry a secondary tone")
        if mode == "integrated_regulation" and self.weights is None:
            raise ValueError("integrated_regulation must retain tone weights")
        if mode == "basic_wellness" and self.weights is not None:
            values = list(self.weights.values())
            if max(values) - min(values) > MODE_WEIGHTS_TOLERANCE:
                raise ValueError("basic_wellness weights must be neutral when present")
        return self


class PublicRationale(V3BaseModel):
    summary: PublicText
    evidence_refs: Annotated[list[NonEmptyString], Field(min_length=1)]


class PublicToneExplanation(V3BaseModel):
    tone: ToneCode
    display_name: PublicText
    explanation: PublicText


class BpmExplanation(V3BaseModel):
    value: Annotated[int, Field(ge=40, le=120)]
    explanation: PublicText


class ListParameterExplanation(V3BaseModel):
    values: Annotated[list[PublicText], Field(min_length=1)]
    explanation: PublicText


class DurationExplanation(V3BaseModel):
    seconds: Annotated[int, Field(gt=0)]
    explanation: PublicText


class GenerationReadiness(V3BaseModel):
    status: Literal["ready", "not_ready"]
    message: PublicText


class FiveToneAnalysisReadModel(V3BaseModel):
    """PUBLIC-only read model for the Five-Tone Analysis / Player basis panel.

    ``regulation_mode`` is the backend authority for the three music-design
    modes; clients must not infer the mode from ``primary_tone == null``.
    ``primary_tone`` is null for ``integrated_regulation`` (balanced weights are
    still present) and for ``basic_wellness`` (no tone conclusion is fabricated).

    Pre-Phase-1A rows (``five_tone_analysis_read_model_v3.1``) are never
    reinterpreted by this model; they are resolved by the legacy compatibility
    resolver, which verifies the stored payload under its own schema/checksum
    semantics first and then derives a modern view.
    """

    schema_version: Literal["five_tone_analysis_read_model_v3.2"]
    confirmed_user_state_ref: ConfirmedUserStateRef
    confirmed_state: PublicText
    state_tendency: PublicText
    analysis_rationales: Annotated[list[PublicRationale], Field(min_length=1)]
    regulation_mode: RegulationMode
    tone_weights: dict[ToneCode, Score01] | None = None
    primary_tone: PublicToneExplanation | None = None
    secondary_tone: PublicToneExplanation | None = None
    bpm: BpmExplanation
    instruments: ListParameterExplanation
    ambience: ListParameterExplanation
    duration: DurationExplanation
    generation: GenerationReadiness
    disclaimer: PublicText

    @model_validator(mode="after")
    def validate_mode_consistency(self) -> "FiveToneAnalysisReadModel":
        if self.tone_weights is not None:
            if set(self.tone_weights) != set(ToneCode):
                raise ValueError("tone weights require all five tones")
            if abs(sum(self.tone_weights.values()) - 1.0) > MODE_WEIGHTS_TOLERANCE:
                raise ValueError("tone weights must sum to 1 ± 0.001")
        if (
            self.secondary_tone is not None
            and self.primary_tone is not None
            and self.secondary_tone.tone == self.primary_tone.tone
        ):
            raise ValueError("secondary tone must differ from primary tone")
        mode = self.regulation_mode
        if mode == "personalized_five_tone":
            if self.primary_tone is None:
                raise ValueError("personalized_five_tone requires a primary tone")
            if self.tone_weights is None:
                raise ValueError("personalized_five_tone requires tone weights")
            return self
        if self.primary_tone is not None:
            raise ValueError(f"{mode} must not present a primary tone")
        if self.secondary_tone is not None:
            raise ValueError(f"{mode} must not present a secondary tone")
        if mode == "integrated_regulation" and self.tone_weights is None:
            raise ValueError("integrated_regulation must retain tone weights")
        if mode == "basic_wellness" and self.tone_weights is not None:
            values = list(self.tone_weights.values())
            if max(values) - min(values) > MODE_WEIGHTS_TOLERANCE:
                raise ValueError("basic_wellness weights must be neutral when present")
        return self

"""Frozen V3 contracts for Agent 1 assessment."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from .common import (
    Conflict,
    Degradation,
    ElementCode,
    EvidenceDirection,
    MissingInformation,
    NonEmptyString,
    NormalizedFactValue,
    OrganCode,
    OrganProfile,
    SafetyStatus,
    Score01,
    SourceRef,
    UserGoal,
    V3BaseModel,
)


class UnderstandingRef(V3BaseModel):
    understanding_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]


class QuestionnaireRef(V3BaseModel):
    questionnaire_submission_id: NonEmptyString
    schema_id: Literal["questionnaire_v3"]
    schema_version: NonEmptyString
    manifest_version: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]


class AssessmentV3Request(V3BaseModel):
    schema_version: Literal["assessment_v3.0"]
    session_id: NonEmptyString
    understanding_ref: UnderstandingRef
    questionnaire_ref: QuestionnaireRef | None
    user_goal: UserGoal


class FactEvidence(V3BaseModel):
    fact_evidence_id: NonEmptyString
    assessment_id: NonEmptyString
    assessment_revision: Annotated[int, Field(ge=1)]
    fact_id: NonEmptyString
    claim_code: NonEmptyString
    display_name: NonEmptyString
    category: NonEmptyString
    value: NormalizedFactValue
    time_window: NonEmptyString
    direction: EvidenceDirection
    reliability: Score01
    source_refs: Annotated[list[SourceRef], Field(min_length=1)]
    confirmation_status: Literal["confirmed", "unconfirmed", "rejected"]


_ORGAN_ELEMENT = {
    OrganCode.liver: ElementCode.wood,
    OrganCode.heart: ElementCode.fire,
    OrganCode.spleen: ElementCode.earth,
    OrganCode.lung: ElementCode.metal,
    OrganCode.kidney: ElementCode.water,
}


class OrganEvidenceLink(V3BaseModel):
    organ_evidence_link_id: NonEmptyString
    fact_evidence_id: NonEmptyString
    organ: OrganCode
    element: ElementCode
    direction: EvidenceDirection
    link_strength: Score01
    mapping_rule_id: NonEmptyString
    mapping_version: NonEmptyString
    explanation_summary: NonEmptyString

    @model_validator(mode="after")
    def organ_and_element_must_match(self) -> "OrganEvidenceLink":
        if _ORGAN_ELEMENT[self.organ] != self.element:
            raise ValueError("organ and element codes are inconsistent")
        return self


class AssessmentPresentation(V3BaseModel):
    title: NonEmptyString
    summary: NonEmptyString
    body_summaries: list[NonEmptyString]
    recent_context: str
    goal_summary: NonEmptyString


class AssessmentV3Response(V3BaseModel):
    schema_version: Literal["assessment_v3.0"]
    agent_id: Literal["assessment_agent"]
    assessment_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]
    status: Literal["needs_confirmation", "confirmed", "degraded", "failed"]
    understanding_ref: UnderstandingRef
    state_summary: NonEmptyString
    recent_context_summary: str
    organ_profile: OrganProfile
    fact_evidence: list[FactEvidence]
    organ_evidence_links: list[OrganEvidenceLink]
    conflicts: list[Conflict]
    missing_information: list[MissingInformation]
    evidence_coverage: Score01
    evidence_coverage_semantics: Literal["confirmed_available_source_coverage"]
    source_diversity: Annotated[int, Field(ge=0)]
    requires_user_confirmation: bool
    safety_status: SafetyStatus
    degradation: Degradation
    presentation: AssessmentPresentation

    @model_validator(mode="after")
    def validate_snapshot_integrity(self) -> "AssessmentV3Response":
        if self.status == "needs_confirmation" and not self.requires_user_confirmation:
            raise ValueError("needs_confirmation must require user confirmation")
        if self.status == "confirmed" and self.requires_user_confirmation:
            raise ValueError("confirmed assessment cannot require user confirmation")

        evidence_ids: set[str] = set()
        fact_ids: set[str] = set()
        for evidence in self.fact_evidence:
            if evidence.fact_evidence_id in evidence_ids or evidence.fact_id in fact_ids:
                raise ValueError("fact evidence must be unique per logical fact")
            if (
                evidence.assessment_id != self.assessment_id
                or evidence.assessment_revision != self.revision
            ):
                raise ValueError("fact evidence must belong to this assessment revision")
            evidence_ids.add(evidence.fact_evidence_id)
            fact_ids.add(evidence.fact_id)

        link_keys: set[tuple[str, OrganCode, str]] = set()
        link_ids: set[str] = set()
        for link in self.organ_evidence_links:
            if link.fact_evidence_id not in evidence_ids:
                raise ValueError("organ evidence link references unknown fact evidence")
            key = (link.fact_evidence_id, link.organ, link.mapping_rule_id)
            if key in link_keys or link.organ_evidence_link_id in link_ids:
                raise ValueError("organ evidence links must be unique")
            link_keys.add(key)
            link_ids.add(link.organ_evidence_link_id)
        return self


class AssessmentRef(V3BaseModel):
    assessment_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]
    confirmation_status: Literal["confirmed"]
    safety_status: SafetyStatus


class AssessmentRevisionChange(V3BaseModel):
    target_type: Literal["fact_evidence"]
    target_id: NonEmptyString
    field: NonEmptyString
    old_value: JsonValue
    new_value: JsonValue
    reason: NonEmptyString | None = None


class AssessmentConfirmationRequest(V3BaseModel):
    expected_revision: Annotated[int, Field(ge=1)]
    decision: Literal["confirm", "confirm_with_changes"]
    changes: list[AssessmentRevisionChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decision_changes(self) -> "AssessmentConfirmationRequest":
        if self.decision == "confirm_with_changes" and not self.changes:
            raise ValueError("confirm_with_changes requires at least one change")
        if self.decision == "confirm" and self.changes:
            raise ValueError("confirm cannot include changes")
        return self


class AssessmentRevisionResult(V3BaseModel):
    assessment_id: NonEmptyString
    previous_revision: Annotated[int, Field(ge=1)]
    revision: Annotated[int, Field(ge=2)]
    confirmation_status: Literal["confirmed", "needs_confirmation"]
    presentation: AssessmentPresentation

    @model_validator(mode="after")
    def revision_must_advance_once(self) -> "AssessmentRevisionResult":
        if self.revision != self.previous_revision + 1:
            raise ValueError("revision must advance exactly once")
        return self

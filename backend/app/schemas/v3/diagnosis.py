"""Frozen V3 contracts for Agent 2, RAG, and diagnosis providers."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field, RootModel, model_validator

from .assessment import AssessmentRef, AssessmentRefV31, FactEvidence, OrganEvidenceLink
from .common import (
    Conflict,
    Degradation,
    ElementProfile,
    MissingInformation,
    NonEmptyString,
    NormalizedFactValue,
    OrganCode,
    OrganProfile,
    SafetyStatus,
    Score01,
    V3BaseModel,
)


class DiagnosisV3Input(V3BaseModel):
    schema_version: Literal["diagnosis_v3.0"]
    diagnosis_id: NonEmptyString
    assessment_ref: AssessmentRef
    organ_profile: OrganProfile
    fact_evidence: list[FactEvidence]
    organ_evidence_links: list[OrganEvidenceLink]
    conflicts: list[Conflict]
    missing_information: list[MissingInformation]

    @model_validator(mode="after")
    def require_safe_confirmed_assessment(self) -> "DiagnosisV3Input":
        if self.assessment_ref.safety_status not in {
            SafetyStatus.clear,
            SafetyStatus.resolved,
        }:
            raise ValueError("diagnosis requires a clear or resolved safety status")
        return self


class DiagnosisV31Input(V3BaseModel):
    """Owner Flow Amendment 001 §4.4 / §6 — Agent 2 input in the new flow.

    The legacy clear/resolved safety gate is replaced by a policy check:
    the confirmed Assessment must be bound to `deferred_v3` with a null
    safety status; it must never be silently mapped through the old gate.
    """

    schema_version: Literal["diagnosis_v3.1"]
    diagnosis_id: NonEmptyString
    assessment_ref: AssessmentRefV31
    organ_profile: OrganProfile
    fact_evidence: list[FactEvidence]
    organ_evidence_links: list[OrganEvidenceLink]
    conflicts: list[Conflict]
    missing_information: list[MissingInformation]

    @model_validator(mode="after")
    def validate_deferred_policy(self) -> "DiagnosisV31Input":
        if self.assessment_ref.safety_policy != "deferred_v3":
            raise ValueError("diagnosis_v3.1 requires deferred_v3 policy")
        if self.assessment_ref.safety_status is not None:
            raise ValueError("deferred_v3 assessment must carry null safety_status")
        return self


class KnowledgeChunk(V3BaseModel):
    chunk_id: NonEmptyString
    source_id: NonEmptyString
    source_title: NonEmptyString
    section: NonEmptyString
    text: NonEmptyString
    display_summary: NonEmptyString
    claim_codes: list[NonEmptyString]
    organ_codes: list[OrganCode]
    review_status: Literal["approved"]
    medical_review_version: NonEmptyString
    knowledge_version: NonEmptyString
    content_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]


class IngestionManifest(V3BaseModel):
    knowledge_version: NonEmptyString
    embedding_provider: NonEmptyString
    embedding_model: NonEmptyString
    embedding_version: NonEmptyString
    distance_metric: NonEmptyString
    retrieval_score_semantics: NonEmptyString
    minimum_score: Score01
    chunk_count: Annotated[int, Field(ge=0)]
    manifest_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    review_status: Literal["approved"]


class RagQuery(V3BaseModel):
    query_id: NonEmptyString
    knowledge_version: NonEmptyString
    ingestion_manifest_checksum: Annotated[str, Field(pattern=r"^sha256:.+")]
    organ_codes: list[OrganCode]
    claim_codes: list[NonEmptyString]
    supporting_fact_ids: list[NonEmptyString]
    contradicting_fact_ids: list[NonEmptyString]
    top_k: Annotated[int, Field(ge=1, le=50)]


class RagHit(V3BaseModel):
    chunk_id: NonEmptyString
    source_id: NonEmptyString
    source_title: NonEmptyString
    section: NonEmptyString
    retrieval_score: Score01
    text: NonEmptyString
    display_summary: NonEmptyString
    review_status: Literal["approved"]


class RagResult(V3BaseModel):
    retrieval_id: NonEmptyString
    status: Literal["success", "empty", "degraded", "failed"]
    knowledge_version: NonEmptyString
    embedding_version: NonEmptyString
    retrieval_score_semantics: NonEmptyString
    hits: list[RagHit]
    degradation: Degradation

    @model_validator(mode="after")
    def validate_result_state(self) -> "RagResult":
        if self.status == "success" and not self.hits:
            raise ValueError("successful retrieval requires at least one hit")
        if self.status in {"empty", "failed"} and self.hits:
            raise ValueError(f"{self.status} retrieval cannot contain hits")
        return self


class DiagnosisProviderFact(V3BaseModel):
    fact_evidence_id: NonEmptyString
    claim_code: NonEmptyString
    value: NormalizedFactValue
    direction: Literal["supporting", "contradicting"]
    time_window: NonEmptyString


class DiagnosisProviderRagRef(V3BaseModel):
    retrieval_id: NonEmptyString
    knowledge_version: NonEmptyString
    chunk_ids: list[NonEmptyString]


class DiagnosisProviderRequest(V3BaseModel):
    request_id: NonEmptyString
    schema_version: Literal["diagnosis_provider_v3.0"]
    response_schema_version: Literal["diagnosis_provider_response_v3.0"]
    prompt_version: NonEmptyString
    assessment_ref: "AssessmentSnapshotRef"
    organ_profile: OrganProfile
    facts: list[DiagnosisProviderFact]
    conflicts: list[Conflict]
    missing_information: list[MissingInformation]
    rag: DiagnosisProviderRagRef | None
    allowed_syndrome_codes: list[NonEmptyString]
    max_candidates: Annotated[int, Field(ge=1, le=3)]


class ProviderCandidateTendency(V3BaseModel):
    syndrome_code: NonEmptyString
    display_name: NonEmptyString
    relative_support: Score01
    supporting_fact_ids: list[NonEmptyString]
    contradicting_fact_ids: list[NonEmptyString]
    knowledge_chunk_ids: list[NonEmptyString]
    reasoning_summary: NonEmptyString

    @model_validator(mode="after")
    def evidence_directions_are_disjoint(self) -> "ProviderCandidateTendency":
        if set(self.supporting_fact_ids) & set(self.contradicting_fact_ids):
            raise ValueError("supporting and contradicting fact ids must be disjoint")
        return self


class DiagnosisProviderResponse(V3BaseModel):
    status: Literal["success", "degraded", "abstained", "failed"]
    candidate_tendencies: Annotated[list[ProviderCandidateTendency], Field(max_length=3)]
    abstained: bool
    abstain_reason: NonEmptyString | None

    @model_validator(mode="after")
    def validate_status_union(self) -> "DiagnosisProviderResponse":
        if self.status in {"success", "degraded"}:
            if self.abstained or not self.candidate_tendencies or self.abstain_reason:
                raise ValueError("successful provider result requires candidates and no abstention")
        elif self.status == "abstained":
            if not self.abstained or self.candidate_tendencies or self.abstain_reason is None:
                raise ValueError("abstained provider result requires reason and no candidates")
        elif self.abstained or self.candidate_tendencies:
            raise ValueError("failed provider result cannot contain candidates or abstention")
        return self


class AssessmentSnapshotRef(V3BaseModel):
    assessment_id: NonEmptyString
    revision: Annotated[int, Field(ge=1)]


class DiagnosisCandidate(ProviderCandidateTendency):
    candidate_id: NonEmptyString


class ExecutionVersions(V3BaseModel):
    prompt_version: NonEmptyString
    response_schema_version: NonEmptyString
    knowledge_version: NonEmptyString
    mapping_version: NonEmptyString


class KnowledgeReference(V3BaseModel):
    title: NonEmptyString
    summary: NonEmptyString


class DiagnosisPresentation(V3BaseModel):
    title: NonEmptyString
    primary_tendency: NonEmptyString | None
    basis_summaries: list[NonEmptyString]
    knowledge_references: list[KnowledgeReference]
    disclaimer: NonEmptyString


class _DiagnosisBase(V3BaseModel):
    schema_version: Literal["diagnosis_v3.0"]
    agent_id: Literal["diagnosis_agent"]
    diagnosis_id: NonEmptyString
    assessment_ref: AssessmentSnapshotRef
    rag_result_ref: NonEmptyString | None
    execution_versions: ExecutionVersions
    degradation: Degradation
    presentation: DiagnosisPresentation

    @model_validator(mode="after")
    def validate_candidate_identity(self) -> "_DiagnosisBase":
        candidate_ids = [item.candidate_id for item in self.candidate_tendencies]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate ids must be unique")
        return self


class SuccessfulDiagnosis(_DiagnosisBase):
    status: Literal["success", "degraded"]
    abstained: Literal[False]
    abstain_reason: None
    candidate_tendencies: Annotated[
        list[DiagnosisCandidate], Field(min_length=1, max_length=3)
    ]
    primary_tendency_id: NonEmptyString
    element_profile: ElementProfile

    @model_validator(mode="after")
    def validate_success_result(self) -> "SuccessfulDiagnosis":
        candidate_ids = {item.candidate_id for item in self.candidate_tendencies}
        if self.primary_tendency_id not in candidate_ids:
            raise ValueError("primary_tendency_id must reference a candidate")
        if self.element_profile.status != "available":
            raise ValueError("success/degraded diagnosis requires available element profile")
        return self


class AbstainedDiagnosis(_DiagnosisBase):
    status: Literal["abstained"]
    abstained: Literal[True]
    abstain_reason: NonEmptyString
    candidate_tendencies: Annotated[list[DiagnosisCandidate], Field(max_length=0)]
    primary_tendency_id: None
    element_profile: ElementProfile

    @model_validator(mode="after")
    def validate_abstained_result(self) -> "AbstainedDiagnosis":
        if self.element_profile.status != "insufficient":
            raise ValueError("abstained diagnosis requires insufficient element profile")
        return self


class WithheldDiagnosis(_DiagnosisBase):
    status: Literal["withheld"]
    abstained: Literal[False]
    abstain_reason: None
    candidate_tendencies: Annotated[list[DiagnosisCandidate], Field(max_length=0)]
    primary_tendency_id: None
    element_profile: ElementProfile

    @model_validator(mode="after")
    def validate_withheld_result(self) -> "WithheldDiagnosis":
        if self.element_profile.status != "insufficient":
            raise ValueError("withheld diagnosis requires insufficient element profile")
        return self


class FailedDiagnosis(_DiagnosisBase):
    status: Literal["failed"]
    abstained: Literal[False]
    abstain_reason: None
    candidate_tendencies: Annotated[list[DiagnosisCandidate], Field(max_length=0)]
    primary_tendency_id: None
    element_profile: ElementProfile

    @model_validator(mode="after")
    def validate_failed_result(self) -> "FailedDiagnosis":
        if self.element_profile.status != "insufficient":
            raise ValueError("failed diagnosis requires insufficient element profile")
        return self


DiagnosisResult: TypeAlias = Annotated[
    SuccessfulDiagnosis | AbstainedDiagnosis | WithheldDiagnosis | FailedDiagnosis,
    Field(discriminator="status"),
]


class DiagnosisV3(RootModel[DiagnosisResult]):
    """Flat externally serialized discriminated Diagnosis response."""

    @property
    def status(self):
        return self.root.status

    @property
    def abstained(self):
        return self.root.abstained

    @property
    def candidate_tendencies(self):
        return self.root.candidate_tendencies

    @property
    def element_profile(self):
        return self.root.element_profile
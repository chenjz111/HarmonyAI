"""V3 diagnosis / RAG / provider-run persistence models.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 6.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class DiagnosisRun(Base):
    __tablename__ = "diagnosis_runs"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id", "assessment_revision", "diagnosis_id",
            name="uq_diagnosis_runs_assessment",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "assessment_revision"],
            ["assessment_revisions_v3.assessment_id", "assessment_revisions_v3.revision"],
            name="fk_diagnosis_runs_assessment",
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'degraded', 'abstained', "
            "'withheld', 'failed')",
            name="ck_diagnosis_runs_status",
        ),
        CheckConstraint(
            "abstained IN (0, 1)", name="ck_diagnosis_runs_abstained"
        ),
        CheckConstraint(
            "abstained = 1 OR abstain_reason IS NULL",
            name="ck_diagnosis_runs_abstain_reason",
        ),
    )

    diagnosis_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    assessment_id = Column(String(64), nullable=False)
    assessment_revision = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False)
    abstained = Column(Integer, nullable=False)
    abstain_reason = Column(String(255), nullable=True)
    primary_tendency_id = Column(String(64), nullable=True)
    element_profile_json = Column(JSON, nullable=True)
    degradation_json = Column(JSON, nullable=False)
    presentation_json = Column(JSON, nullable=False)
    provider_run_id = Column(String(64), nullable=True)
    rag_run_id = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DiagnosisCandidate(Base):
    __tablename__ = "diagnosis_candidates"
    __table_args__ = (
        UniqueConstraint(
            "diagnosis_id", "syndrome_code", name="uq_diagnosis_candidates_syndrome"
        ),
        CheckConstraint(
            "relative_support >= 0 AND relative_support <= 1",
            name="ck_diagnosis_candidates_support",
        ),
        CheckConstraint("rank >= 1", name="ck_diagnosis_candidates_rank"),
    )

    candidate_id = Column(String(64), primary_key=True)
    diagnosis_id = Column(
        String(64),
        ForeignKey("diagnosis_runs.diagnosis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    syndrome_code = Column(String(64), nullable=False)
    display_name = Column(String(255), nullable=False)
    relative_support = Column(Float, nullable=False)
    reasoning_summary = Column(Text, nullable=False)
    rank = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DiagnosisCandidateEvidence(Base):
    __tablename__ = "diagnosis_candidate_evidence"

    candidate_id = Column(
        String(64),
        ForeignKey("diagnosis_candidates.candidate_id", ondelete="CASCADE"),
        primary_key=True,
    )
    fact_evidence_row_id = Column(
        String(64),
        ForeignKey("fact_evidence.fact_evidence_row_id"),
        primary_key=True,
    )
    direction = Column(String(16), nullable=False)


class KnowledgeManifest(Base):
    __tablename__ = "knowledge_manifests"
    __table_args__ = (
        UniqueConstraint("knowledge_version", name="uq_knowledge_manifests_version"),
        UniqueConstraint("manifest_checksum", name="uq_knowledge_manifests_checksum"),
        CheckConstraint(
            "minimum_score >= 0 AND minimum_score <= 1",
            name="ck_knowledge_manifests_minimum_score",
        ),
        CheckConstraint(
            "chunk_count >= 0", name="ck_knowledge_manifests_chunk_count"
        ),
        CheckConstraint(
            "review_status IN ('approved', 'pending', 'rejected')",
            name="ck_knowledge_manifests_review",
        ),
    )

    knowledge_manifest_id = Column(String(64), primary_key=True)
    knowledge_version = Column(String(64), nullable=False)
    embedding_provider = Column(String(64), nullable=False)
    embedding_model = Column(String(64), nullable=False)
    embedding_version = Column(String(64), nullable=False)
    distance_metric = Column(String(16), nullable=False)
    score_semantics = Column(String(64), nullable=False)
    minimum_score = Column(Float, nullable=False)
    chunk_count = Column(Integer, nullable=False)
    manifest_checksum = Column(String(96), nullable=False)
    review_status = Column(String(16), nullable=False)
    medical_review_version = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeChunkV3(Base):
    __tablename__ = "knowledge_chunks_v3"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_manifest_id", "chunk_id", name="uq_knowledge_chunks_id"
        ),
    )

    chunk_row_id = Column(String(64), primary_key=True)
    knowledge_manifest_id = Column(
        String(64),
        ForeignKey("knowledge_manifests.knowledge_manifest_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id = Column(String(64), nullable=False)
    source_id = Column(String(64), nullable=False)
    source_title = Column(String(255), nullable=False)
    section = Column(String(64), nullable=False)
    text_ciphertext = Column(Text, nullable=False)
    display_summary = Column(Text, nullable=False)
    claim_codes_json = Column(JSON, nullable=False)
    organ_codes_json = Column(JSON, nullable=False)
    content_checksum = Column(String(96), nullable=False)
    review_status = Column(String(16), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RagRetrievalRun(Base):
    __tablename__ = "rag_retrieval_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'degraded', 'failed', 'empty')",
            name="ck_rag_retrieval_runs_status",
        ),
        CheckConstraint("top_k >= 1", name="ck_rag_retrieval_runs_top_k"),
        CheckConstraint(
            "minimum_score >= 0 AND minimum_score <= 1",
            name="ck_rag_retrieval_runs_minimum_score",
        ),
    )

    rag_run_id = Column(String(64), primary_key=True)
    diagnosis_id = Column(
        String(64),
        ForeignKey("diagnosis_runs.diagnosis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_hash = Column(String(96), nullable=False)
    query_builder_version = Column(String(32), nullable=False)
    knowledge_manifest_id = Column(
        String(64),
        ForeignKey("knowledge_manifests.knowledge_manifest_id"),
        nullable=False,
    )
    knowledge_version = Column(String(64), nullable=False)
    manifest_checksum = Column(String(96), nullable=False)
    embedding_version = Column(String(64), nullable=False)
    distance_metric = Column(String(16), nullable=False)
    score_semantics = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    top_k = Column(Integer, nullable=False)
    minimum_score = Column(Float, nullable=False)
    degradation_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RagRetrievalHit(Base):
    __tablename__ = "rag_retrieval_hits"
    __table_args__ = (
        CheckConstraint(
            "retrieval_score >= 0 AND retrieval_score <= 1",
            name="ck_rag_retrieval_hits_score",
        ),
    )

    rag_run_id = Column(
        String(64),
        ForeignKey("rag_retrieval_runs.rag_run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    chunk_id = Column(String(64), primary_key=True)
    source_id = Column(String(64), nullable=False)
    source_title = Column(String(255), nullable=False)
    section = Column(String(64), nullable=False)
    retrieval_score = Column(Float, nullable=False)
    display_summary = Column(Text, nullable=False)
    text_ciphertext = Column(Text, nullable=False)
    review_status = Column(String(16), nullable=False)
    knowledge_version = Column(String(64), nullable=False)
    chunk_content_checksum = Column(String(96), nullable=False)


class AiProviderRun(Base):
    __tablename__ = "ai_provider_runs"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('understanding', 'diagnosis', 'schema_repair')",
            name="ck_ai_provider_runs_purpose",
        ),
        CheckConstraint("attempts >= 1", name="ck_ai_provider_runs_attempts"),
        CheckConstraint("latency_ms >= 0", name="ck_ai_provider_runs_latency"),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_provider_runs_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_provider_runs_output_tokens",
        ),
    )

    provider_run_id = Column(String(64), primary_key=True)
    purpose = Column(String(16), nullable=False)
    resource_id = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(64), nullable=True)
    prompt_version = Column(String(32), nullable=False)
    response_schema_version = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False)
    error_code = Column(String(32), nullable=True)
    attempts = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    request_hash = Column(String(96), nullable=True)
    response_hash = Column(String(96), nullable=True)
    knowledge_version = Column(String(64), nullable=True)
    mapping_version = Column(String(32), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

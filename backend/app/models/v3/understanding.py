"""V3 information-understanding persistence models.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 4.
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


class UnderstandingRun(Base):
    __tablename__ = "understanding_runs"
    __table_args__ = (
        UniqueConstraint(
            "understanding_id", "internal_user_pk", name="uq_understanding_runs_user"
        ),
        CheckConstraint("current_revision >= 1", name="ck_understanding_runs_revision"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'needs_confirmation', "
            "'confirmed', 'degraded', 'failed')",
            name="ck_understanding_runs_status",
        ),
        CheckConstraint(
            "flow_contract_version IS NULL OR "
            "flow_contract_version = 'v3-owner-flow-1'",
            name="ck_understanding_runs_flow_contract",
        ),
        CheckConstraint(
            "input_revision IS NULL OR input_revision >= 1",
            name="ck_understanding_runs_input_revision",
        ),
        CheckConstraint(
            "safety_policy IS NULL OR safety_policy = 'deferred_v3'",
            name="ck_understanding_runs_safety_policy",
        ),
        CheckConstraint(
            "safety_evaluation_status IS NULL OR "
            "safety_evaluation_status = 'not_run'",
            name="ck_understanding_runs_safety_eval",
        ),
    )

    understanding_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    current_revision = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False)
    # New v3-owner-flow-1 rows set safety_status=NULL (deferred_v3); legacy
    # rows keep a concrete SafetyStatus. See Owner Flow Amendment 001 §13.3.
    safety_status = Column(String(32), nullable=True)
    flow_contract_version = Column(String(32), nullable=True)
    input_revision = Column(Integer, nullable=True)
    safety_policy = Column(String(32), nullable=True)
    safety_evaluation_status = Column(String(32), nullable=True)
    degradation_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UnderstandingSource(Base):
    __tablename__ = "understanding_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('document', 'case_summary', 'narrative', "
            "'voice_transcript', 'questionnaire', 'user_correction')",
            name="ck_understanding_sources_type",
        ),
        CheckConstraint(
            "processing_status IN ('uploading', 'processing', "
            "'needs_confirmation', 'ready', 'degraded', 'failed', 'skipped')",
            name="ck_understanding_sources_status",
        ),
        CheckConstraint(
            "(CASE WHEN document_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN audio_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN questionnaire_submission_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
            name="ck_understanding_sources_single",
        ),
    )

    source_id = Column(String(64), primary_key=True)
    understanding_id = Column(
        String(64),
        ForeignKey("understanding_runs.understanding_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type = Column(String(24), nullable=False)
    processing_status = Column(String(24), nullable=False)
    document_id = Column(String(64), nullable=True)
    audio_id = Column(String(64), nullable=True)
    questionnaire_submission_id = Column(String(64), nullable=True)
    text_ciphertext = Column(Text, nullable=True)
    text_hash = Column(String(96), nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UnderstandingRevision(Base):
    __tablename__ = "understanding_revisions"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_understanding_revisions_revision"),
        CheckConstraint(
            "status IN ('needs_confirmation', 'confirmed', 'degraded')",
            name="ck_understanding_revisions_status",
        ),
        CheckConstraint(
            "confirmation_decision IS NULL OR confirmation_decision IN "
            "('confirm', 'confirm_with_changes', 'reject_source', 'cannot_confirm')",
            name="ck_understanding_revisions_decision",
        ),
        CheckConstraint(
            "confirmed_at IS NULL OR confirmation_decision IS NOT NULL",
            name="ck_understanding_revisions_confirmed",
        ),
    )

    understanding_id = Column(
        String(64),
        ForeignKey("understanding_runs.understanding_id", ondelete="CASCADE"),
        primary_key=True,
    )
    revision = Column(Integer, primary_key=True)
    previous_revision = Column(Integer, nullable=True)
    status = Column(String(24), nullable=False)
    case_summary_json = Column(JSON, nullable=True)
    presentation_json = Column(JSON, nullable=False)
    confirmation_decision = Column(String(32), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class QuestionnaireSubmissionV3(Base):
    __tablename__ = "questionnaire_submissions_v3"
    __table_args__ = (
        UniqueConstraint(
            "internal_user_pk", "idempotency_key", name="uq_questionnaire_submissions_idem"
        ),
        CheckConstraint(
            "schema_id = 'questionnaire_v3'", name="ck_questionnaire_submissions_schema"
        ),
        CheckConstraint(
            "content_checksum LIKE 'sha256:%'",
            name="ck_questionnaire_submissions_checksum",
        ),
        CheckConstraint(
            "time_window_days = 7", name="ck_questionnaire_submissions_window"
        ),
    )

    questionnaire_submission_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    schema_id = Column(String(32), nullable=False)
    schema_version = Column(String(32), nullable=False)
    manifest_version = Column(String(32), nullable=False)
    content_checksum = Column(String(96), nullable=False)
    time_window_days = Column(Integer, nullable=False)
    answers_json = Column(JSON, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)


class NormalizedFact(Base):
    __tablename__ = "normalized_facts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["understanding_id", "understanding_revision"],
            ["understanding_revisions.understanding_id", "understanding_revisions.revision"],
            name="fk_normalized_facts_revision",
        ),
        ForeignKeyConstraint(
            ["questionnaire_submission_id"],
            ["questionnaire_submissions_v3.questionnaire_submission_id"],
            name="fk_normalized_facts_questionnaire",
        ),
        UniqueConstraint(
            "understanding_id", "understanding_revision", "fact_id",
            name="uq_normalized_facts_understanding",
        ),
        UniqueConstraint(
            "questionnaire_submission_id", "fact_id",
            name="uq_normalized_facts_questionnaire",
        ),
        CheckConstraint(
            "owner_type IN ('understanding', 'questionnaire')",
            name="ck_normalized_facts_owner",
        ),
        CheckConstraint(
            "(owner_type = 'understanding' AND understanding_id IS NOT NULL "
            "AND understanding_revision IS NOT NULL "
            "AND questionnaire_submission_id IS NULL) OR "
            "(owner_type = 'questionnaire' AND questionnaire_submission_id IS NOT NULL "
            "AND understanding_id IS NULL AND understanding_revision IS NULL)",
            name="ck_normalized_facts_owner_exclusive",
        ),
        CheckConstraint(
            "negated IN (0, 1)", name="ck_normalized_facts_negated"
        ),
        CheckConstraint(
            "subject IN ('self', 'other', 'unknown')",
            name="ck_normalized_facts_subject",
        ),
        CheckConstraint(
            "confirmation_status IN ('confirmed', 'unconfirmed', 'rejected')",
            name="ck_normalized_facts_confirmation",
        ),
        CheckConstraint(
            "extraction_method IN ('qwen', 'rule', 'user_correction', "
            "'deterministic_questionnaire_mapping')",
            name="ck_normalized_facts_method",
        ),
        CheckConstraint(
            "extraction_confidence IS NULL OR "
            "(extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="ck_normalized_facts_confidence",
        ),
    )

    fact_row_id = Column(String(64), primary_key=True)
    fact_id = Column(String(64), nullable=False)
    owner_type = Column(String(16), nullable=False)
    understanding_id = Column(String(64), nullable=True)
    understanding_revision = Column(Integer, nullable=True)
    questionnaire_submission_id = Column(String(64), nullable=True)
    fact_code = Column(String(64), nullable=False)
    category = Column(String(32), nullable=False)
    display_name = Column(String(255), nullable=False)
    value_json = Column(JSON, nullable=False)
    time_window = Column(String(16), nullable=False)
    negated = Column(Integer, nullable=False)
    subject = Column(String(16), nullable=False)
    confirmation_status = Column(String(16), nullable=False)
    extraction_method = Column(String(32), nullable=False)
    extraction_confidence = Column(Float, nullable=True)
    supersedes_fact_row_id = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FactSourceRef(Base):
    __tablename__ = "fact_source_refs"

    fact_row_id = Column(
        String(64),
        ForeignKey("normalized_facts.fact_row_id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_type = Column(String(24), primary_key=True)
    source_id = Column(String(64), primary_key=True)
    span_ref = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

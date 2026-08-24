"""V3 assessment persistence models.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 5.
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


class AssessmentV3(Base):
    __tablename__ = "assessment_v3"
    __table_args__ = (
        UniqueConstraint("session_row_id", "assessment_id", name="uq_assessment_v3_session"),
        ForeignKeyConstraint(
            ["understanding_id", "understanding_revision"],
            ["understanding_revisions.understanding_id", "understanding_revisions.revision"],
            name="fk_assessment_v3_understanding",
        ),
        ForeignKeyConstraint(
            ["questionnaire_submission_id"],
            ["questionnaire_submissions_v3.questionnaire_submission_id"],
            name="fk_assessment_v3_questionnaire",
        ),
        CheckConstraint(
            "current_revision >= 1", name="ck_assessment_v3_revision"
        ),
        CheckConstraint(
            "status IN ('needs_confirmation', 'confirmed', 'degraded', 'withheld')",
            name="ck_assessment_v3_status",
        ),
    )

    assessment_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    understanding_id = Column(String(64), nullable=False)
    understanding_revision = Column(Integer, nullable=False)
    questionnaire_submission_id = Column(String(64), nullable=True)
    current_revision = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False)
    safety_status = Column(String(32), nullable=False)
    user_goal_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AssessmentRevisionV3(Base):
    __tablename__ = "assessment_revisions_v3"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_assessment_revisions_revision"),
        CheckConstraint(
            "evidence_coverage >= 0 AND evidence_coverage <= 1",
            name="ck_assessment_revisions_evidence",
        ),
        CheckConstraint(
            "source_diversity >= 0", name="ck_assessment_revisions_diversity"
        ),
        CheckConstraint(
            "confirmed_at IS NULL OR confirmation_status = 'confirmed'",
            name="ck_assessment_revisions_confirmed",
        ),
    )

    assessment_id = Column(
        String(64),
        ForeignKey("assessment_v3.assessment_id", ondelete="CASCADE"),
        primary_key=True,
    )
    revision = Column(Integer, primary_key=True)
    previous_revision = Column(Integer, nullable=True)
    understanding_revision = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False)
    confirmation_status = Column(String(16), nullable=False)
    state_summary = Column(Text, nullable=False)
    recent_context_summary = Column(Text, nullable=True)
    organ_profile_json = Column(JSON, nullable=False)
    evidence_coverage = Column(Float, nullable=False)
    source_diversity = Column(Integer, nullable=False)
    conflicts_json = Column(JSON, nullable=False)
    missing_information_json = Column(JSON, nullable=False)
    degradation_json = Column(JSON, nullable=False)
    presentation_json = Column(JSON, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FactEvidence(Base):
    __tablename__ = "fact_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assessment_id", "assessment_revision"],
            ["assessment_revisions_v3.assessment_id", "assessment_revisions_v3.revision"],
            name="fk_fact_evidence_revision",
        ),
        UniqueConstraint(
            "assessment_id", "assessment_revision", "fact_evidence_id",
            name="uq_fact_evidence_id",
        ),
        CheckConstraint(
            "direction IN ('supporting', 'contradicting')",
            name="ck_fact_evidence_direction",
        ),
        CheckConstraint(
            "reliability >= 0 AND reliability <= 1",
            name="ck_fact_evidence_reliability",
        ),
        CheckConstraint(
            "confirmation_status IN ('confirmed', 'unconfirmed', 'rejected')",
            name="ck_fact_evidence_confirmation",
        ),
    )

    fact_evidence_row_id = Column(String(64), primary_key=True)
    fact_evidence_id = Column(String(64), nullable=False)
    assessment_id = Column(String(64), nullable=False)
    assessment_revision = Column(Integer, nullable=False)
    normalized_fact_row_id = Column(
        String(64),
        ForeignKey("normalized_facts.fact_row_id"),
        nullable=False,
        index=True,
    )
    claim_code = Column(String(64), nullable=False)
    category = Column(String(32), nullable=False)
    display_name = Column(String(255), nullable=False)
    value_json = Column(JSON, nullable=False)
    time_window = Column(String(16), nullable=False)
    direction = Column(String(16), nullable=False)
    reliability = Column(Float, nullable=False)
    confirmation_status = Column(String(16), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OrganEvidence(Base):
    __tablename__ = "organ_evidence"
    __table_args__ = (
        UniqueConstraint(
            "fact_evidence_row_id", "organ", "mapping_rule_id",
            name="uq_organ_evidence_link",
        ),
        CheckConstraint(
            "organ IN ('liver', 'heart', 'spleen', 'lung', 'kidney')",
            name="ck_organ_evidence_organ",
        ),
        CheckConstraint(
            "element IN ('wood', 'fire', 'earth', 'metal', 'water')",
            name="ck_organ_evidence_element",
        ),
        CheckConstraint(
            "direction IN ('supporting', 'contradicting')",
            name="ck_organ_evidence_direction",
        ),
        CheckConstraint(
            "link_strength >= 0 AND link_strength <= 1",
            name="ck_organ_evidence_strength",
        ),
    )

    organ_evidence_link_id = Column(String(64), primary_key=True)
    fact_evidence_row_id = Column(
        String(64),
        ForeignKey("fact_evidence.fact_evidence_row_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organ = Column(String(16), nullable=False)
    element = Column(String(16), nullable=False)
    direction = Column(String(16), nullable=False)
    link_strength = Column(Float, nullable=False)
    mapping_rule_id = Column(String(64), nullable=False)
    mapping_version = Column(String(32), nullable=False)
    explanation_summary = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

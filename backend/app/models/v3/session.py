"""V3 session-supporting persistence models."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class V3IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "internal_user_pk",
            "operation",
            "idempotency_key",
            name="uq_idempotency_owner_operation",
        ),
        CheckConstraint(
            "status IN ('processing', 'succeeded', 'failed')",
            name="ck_idempotency_status",
        ),
    )

    idempotency_record_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_hash = Column(String(96), nullable=False)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False)
    response_code = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)


class SessionInputRevision(Base):
    """Immutable audit snapshot of a session's active-input state (Owner Flow
    Amendment 001 §13.1). One row per (session_row_id, input_revision).

    Reference columns are validated at the service layer (same user / same
    session / OCR / confirmed status); hard FKs are attached only where they
    do not create a cycle with the V3 business tables.
    """

    __tablename__ = "session_input_revisions"
    __table_args__ = (
        UniqueConstraint(
            "session_row_id",
            "input_revision",
            name="uq_session_input_revisions_session_revision",
        ),
        CheckConstraint(
            "input_revision >= 1",
            name="ck_session_input_revisions_revision",
        ),
        CheckConstraint(
            "input_mode IS NULL OR input_mode IN ('with_document', 'without_document')",
            name="ck_session_input_revisions_mode",
        ),
        CheckConstraint(
            "action IN ('create', 'select_mode', 'replace_document', "
            "'discard_document', 'confirm_source', 'submit_questionnaire')",
            name="ck_session_input_revisions_action",
        ),
        CheckConstraint(
            "(active_understanding_id IS NULL AND active_understanding_revision IS NULL) "
            "OR (active_understanding_id IS NOT NULL "
            "AND active_understanding_revision IS NOT NULL)",
            name="ck_session_input_revisions_understanding_pair",
        ),
        ForeignKeyConstraint(
            ["active_understanding_id", "active_understanding_revision"],
            [
                "understanding_revisions.understanding_id",
                "understanding_revisions.revision",
            ],
            name="fk_session_input_revisions_understanding",
        ),
        ForeignKeyConstraint(
            ["active_questionnaire_submission_id"],
            ["questionnaire_submissions_v3.questionnaire_submission_id"],
            name="fk_session_input_revisions_questionnaire",
        ),
    )

    session_row_id = Column(
        Integer, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    input_revision = Column(Integer, primary_key=True)
    input_mode = Column(String(16), nullable=True)
    active_document_id = Column(String(64), nullable=True)
    active_understanding_id = Column(String(64), nullable=True)
    active_understanding_revision = Column(Integer, nullable=True)
    active_questionnaire_submission_id = Column(String(64), nullable=True)
    action = Column(String(32), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

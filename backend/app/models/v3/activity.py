"""V3 session activity state (Owner Flow Amendment 001 §4.1)."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from backend.app.core.database import Base


class V3SessionActivity(Base):
    __tablename__ = "v3_session_activities"
    __table_args__ = (
        CheckConstraint(
            "input_revision >= 1",
            name="ck_v3_session_activity_revision",
        ),
        CheckConstraint(
            "input_mode IS NULL OR input_mode IN "
            "('with_document', 'without_document')",
            name="ck_v3_session_activity_mode",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flow_contract_version = Column(String(32), nullable=True)
    input_mode = Column(String(16), nullable=True)
    input_revision = Column(Integer, nullable=False, default=1)
    active_document_id = Column(String(64), nullable=True)
    understanding_ref = Column(Text, nullable=True, comment="JSON {understanding_id, revision}")
    questionnaire_ref = Column(Text, nullable=True, comment="JSON questionnaire submission ref")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )

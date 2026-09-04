"""Session model — tracks user conversation sessions."""
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "input_mode IS NULL OR input_mode IN ('with_document', 'without_document')",
            name="ck_sessions_input_mode",
        ),
        CheckConstraint(
            "input_revision IS NULL OR input_revision >= 1",
            name="ck_sessions_input_revision",
        ),
        CheckConstraint(
            "flow_contract_version IS NULL OR "
            "flow_contract_version = 'v3-owner-flow-1'",
            name="ck_sessions_flow_contract",
        ),
        CheckConstraint(
            "safety_policy IS NULL OR safety_policy = 'deferred_v3'",
            name="ck_sessions_safety_policy",
        ),
        CheckConstraint(
            "(active_understanding_id IS NULL AND active_understanding_revision IS NULL) "
            "OR (active_understanding_id IS NOT NULL "
            "AND active_understanding_revision IS NOT NULL)",
            name="ck_sessions_understanding_pair",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="FK→users.id",
    )
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment="会话ID: sess_YYYYMMDD_NNN")
    status = Column(String(16), default="active", comment="active / completed / abandoned")
    current_agent = Column(String(32), nullable=True, comment="当前所在Agent: evaluation/diagnosis/prescription/generation/feedback")
    metadata_json = Column(Text, nullable=True, comment="会话元数据 JSON")
    flow_version = Column(
        String(16), nullable=True, comment="V3 writes v3; V2 rows may be null"
    )
    input_mode = Column(
        String(16),
        nullable=True,
        comment="V3 entry choice persisted: with_document / without_document",
    )
    # Owner Flow Amendment 001 (v3-owner-flow-1) session activity columns.
    # Reference columns are validated at the service layer (same user / same
    # session / OCR / confirmed status); they are deliberately not hard SQL
    # FKs to avoid a circular FK back into the V3 business tables.
    flow_contract_version = Column(
        String(32),
        nullable=True,
        comment="V3 flow contract: v3-owner-flow-1 (immutable once bound)",
    )
    input_revision = Column(
        Integer,
        nullable=True,
        comment="Active-input revision; CAS-incremented on source changes",
    )
    safety_policy = Column(
        String(32),
        nullable=True,
        comment="New-flow safety policy: deferred_v3 (server-set)",
    )
    active_document_id = Column(String(64), nullable=True)
    active_document_set_id = Column(String(64), nullable=True)
    active_understanding_id = Column(String(64), nullable=True)
    active_understanding_revision = Column(Integer, nullable=True)
    active_questionnaire_submission_id = Column(String(64), nullable=True)
    user_goal_json = Column(
        JSON,
        nullable=True,
        comment="V3.1 疗愈诉求（选填，仅供 Agent3 音乐设计/个性化）",
    )

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Session(session_id={self.session_id}, status={self.status})>"

"""Assessment revision — Sprint 4: tracks changes to assessment results."""
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AssessmentRevision(Base):
    __tablename__ = "assessment_revisions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "revision", name="uq_assessment_revision"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    assessment_id = Column(String(64), nullable=True, index=True)
    revision_id = Column(String(64), unique=True, nullable=False)
    revision = Column(Integer, nullable=True)
    previous_revision = Column(Integer, nullable=True)
    change_summary = Column(Text, nullable=True)
    changes = Column(JSON, nullable=True)
    assessment_snapshot = Column(JSON, nullable=True)
    confirmation_level = Column(String(32), nullable=True)
    field_changed = Column(String(64), nullable=False, comment="Which field was revised")
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=False)
    source = Column(String(32), nullable=False, comment="user_confirmation/followup_answer/ocr_confirmation")
    created_at = Column(DateTime, server_default=func.now())

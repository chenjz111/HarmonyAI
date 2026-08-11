"""Assessment follow-up — Sprint 4: follow-up questions for missing information."""
from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AssessmentFollowUp(Base):
    __tablename__ = "assessment_followups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    assessment_id = Column(String(64), nullable=True, index=True)
    followup_id = Column(String(64), unique=True, nullable=False)
    question_id = Column(String(64), nullable=True)
    question = Column(Text, nullable=False, comment="Follow-up question text")
    category = Column(String(32), nullable=False, comment="emotion/body/sleep/clarification")
    priority = Column(Integer, default=1, comment="1=highest")
    status = Column(String(16), default="pending", comment="pending/answered/ignored")
    answer = Column(Text, nullable=True)
    answer_value = Column(JSON, nullable=True)
    source_type = Column(String(32), nullable=True)
    revision_submitted = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

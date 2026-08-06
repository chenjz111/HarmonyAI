"""Assessment follow-up — Sprint 4: follow-up questions for missing information."""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AssessmentFollowUp(Base):
    __tablename__ = "assessment_followups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    followup_id = Column(String(64), unique=True, nullable=False)
    question = Column(Text, nullable=False, comment="Follow-up question text")
    category = Column(String(32), nullable=False, comment="emotion/body/sleep/clarification")
    priority = Column(Integer, default=1, comment="1=highest")
    status = Column(String(16), default="pending", comment="pending/answered/ignored")
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

"""Assessment evidence — Sprint 4: individual pieces of evidence for diagnosis."""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func
from backend.app.core.database import Base


class AssessmentEvidence(Base):
    __tablename__ = "assessment_evidences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    evidence_id = Column(String(64), unique=True, nullable=False)
    source = Column(String(32), nullable=False, comment="questionnaire/document/narrative/provider")
    category = Column(String(32), nullable=False, comment="emotion/body/sleep/medical_history")
    content = Column(Text, nullable=False, comment="Evidence text")
    confidence = Column(Float, nullable=False)
    used_in_diagnosis = Column(Integer, default=1, comment="0=excluded 1=included")
    created_at = Column(DateTime, server_default=func.now())

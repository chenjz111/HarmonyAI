"""Assessment evidence — Sprint 4: individual pieces of evidence for diagnosis."""
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text
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
    # Sprint 4 Frozen Contract fields. Legacy columns above remain for
    # backward-compatible reads during the incremental migration.
    label = Column(String(64), nullable=True)
    display_name = Column(String(128), nullable=True)
    value = Column(JSON, nullable=True)
    polarity = Column(String(16), nullable=True)
    severity = Column(String(16), nullable=True)
    severity_display = Column(String(64), nullable=True)
    time_window = Column(String(64), nullable=True)
    source_type = Column(String(32), nullable=True)
    source_ref = Column(String(128), nullable=True)
    quote = Column(Text, nullable=True)
    extraction_confidence = Column(Float, nullable=True)
    confirmed = Column(Boolean, nullable=False, default=False)
    dimension_score = Column(Integer, nullable=True)
    used_in_diagnosis = Column(Integer, default=1, comment="0=excluded 1=included")
    created_at = Column(DateTime, server_default=func.now())

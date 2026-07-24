"""Syndrome Diagnosis model — stores Agent ② (diagnosis_agent) output.

Maps to agent-schemas.md Agent ② 中医辨证Agent output schema.
MVP table: syndrome_diagnoses
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean
from sqlalchemy.sql import func

from backend.app.core.database import Base


class SyndromeDiagnosis(Base):
    __tablename__ = "syndrome_diagnoses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)

    # Agent metadata
    agent_id = Column(String(64), default="diagnosis_agent", nullable=False)
    agent_version = Column(String(16), default="1.0.0", nullable=False)

    # Primary syndrome
    primary_name = Column(String(64), nullable=False, comment="主证型名称 如'肝郁化火'")
    primary_element = Column(String(8), nullable=True, comment="五行: 木/火/土/金/水")
    primary_organ = Column(String(8), nullable=True, comment="五脏: 肝/心/脾/肺/肾")
    primary_emotion = Column(String(8), nullable=True, comment="情绪: 怒/喜/思/悲/恐")
    primary_severity_level = Column(Integer, nullable=True, comment="严重程度 1-5")
    primary_severity_name = Column(String(16), nullable=True, comment="轻度/中度/重度")

    # Secondary syndromes JSON
    secondary_syndromes = Column(Text, nullable=True, comment="兼证列表 JSON")

    # Confidence breakdown
    confidence_overall = Column(Float, nullable=False, comment="整体可信度")
    confidence_rule_engine = Column(Float, nullable=True)
    confidence_llm = Column(Float, nullable=True)
    confidence_literature = Column(Float, nullable=True)

    # Evidence & keywords
    evidence = Column(Text, nullable=True, comment="文献证据 JSON")
    search_keywords = Column(Text, nullable=True, comment="RAG检索关键词 JSON")

    # Warnings
    warn_low_confidence = Column(Boolean, default=False)
    warn_conflicting = Column(Boolean, default=False)
    warn_recommend_professional = Column(Boolean, default=False)

    # 通用字段
    confidence = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<SyndromeDiagnosis(id={self.id}, primary={self.primary_name})>"

"""Emotion Assessment model — stores Agent ① (evaluation_agent) output.

Maps to agent-schemas.md Agent ① 评估Agent output schema.
MVP table: emotion_assessments
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func

from backend.app.core.database import Base


class EmotionAssessment(Base):
    __tablename__ = "emotion_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID: sess_YYYYMMDD_NNN")

    # Agent metadata (通用字段)
    agent_id = Column(String(64), default="evaluation_agent", nullable=False)
    agent_version = Column(String(16), default="1.0.0", nullable=False)
    input_channel = Column(String(32), nullable=False, comment="输入渠道: questionnaire")

    # raw_input JSON
    raw_input = Column(Text, nullable=True, comment="原始输入 JSON")

    # health_profile → emotion_scores (core data for Agent ①)
    emotion_anxiety = Column(Float, nullable=True, comment="焦虑分数 0-100")
    emotion_depression = Column(Float, nullable=True, comment="抑郁分数 0-100")
    emotion_anger = Column(Float, nullable=True, comment="愤怒分数 0-100")
    emotion_fear = Column(Float, nullable=True, comment="恐惧分数 0-100")
    emotion_overthinking = Column(Float, nullable=True, comment="思虑分数 0-100")

    # body_indicators
    body_sleep_quality = Column(Float, nullable=True, comment="睡眠质量 0-100")
    body_appetite = Column(Float, nullable=True, comment="食欲 0-100")
    body_energy = Column(Float, nullable=True, comment="精力 0-100")
    body_palpitation = Column(Float, nullable=True, comment="心悸 0-100")
    body_digestion = Column(Float, nullable=True, comment="消化 0-100")

    # questionnaire_scores
    questionnaire_total = Column(Float, nullable=True, comment="问卷总分")
    questionnaire_emotion = Column(Float, nullable=True, comment="情绪维度")
    questionnaire_sleep = Column(Float, nullable=True, comment="睡眠维度")
    questionnaire_body = Column(Float, nullable=True, comment="身体维度")

    # term_mapping JSON
    term_mapping = Column(Text, nullable=True, comment="西医→中医术语映射 JSON")

    # 通用字段
    confidence = Column(Float, nullable=False, comment="整体可信度 0-1")
    reason = Column(Text, nullable=True, comment="决策依据 JSON")
    processing_time_ms = Column(Integer, nullable=True, comment="处理耗时(ms)")
    timestamp = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<EmotionAssessment(id={self.id}, user_id={self.user_id})>"

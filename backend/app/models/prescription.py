"""Prescription model — stores Agent ③ + ④ output (merged per MVP).

Maps to agent-schemas.md Agent ③ 音乐处方Agent + Agent ④ 音乐生成Agent.
MVP table: prescriptions

Design: daily_plan is stored as JSON text because it contains a variable-length
array of days. Audio generation data is merged into this table (not separate)
per MVP definition §3.
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.sql import func

from backend.app.core.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)

    # Agent metadata
    agent_id = Column(String(64), default="prescription_agent", nullable=False)
    agent_version = Column(String(16), default="1.0.0", nullable=False)
    prescription_id = Column(String(64), unique=True, nullable=False, index=True, comment="处方ID: rx_YYYYMMDD_NNN")

    # ── Agent ③: Daily plan ──
    daily_plan = Column(Text, nullable=False, comment="每日处方计划 JSON 数组 (7天)")
    prompt_template_id = Column(String(32), nullable=True, comment="模板ID 如 CN_V1")
    prompt_template_version = Column(String(16), nullable=True)
    prompt_parameters = Column(Text, nullable=True, comment="Prompt参数 JSON")

    # Explanation
    explanation_summary = Column(Text, nullable=True, comment="中医解释摘要")
    explanation_user_facing = Column(Text, nullable=True, comment="用户端解释文本")
    explanation_warnings = Column(Text, nullable=True, comment="警告列表 JSON")

    # ── Agent ④: Audio generation (merged from generations table) ──
    audio_url = Column(Text, nullable=True, comment="音频OSS URL")
    audio_duration_seconds = Column(Integer, nullable=True)
    audio_file_size_bytes = Column(Integer, nullable=True)
    audio_format = Column(String(8), nullable=True, default="mp3")
    audio_bitrate_kbps = Column(Integer, nullable=True)
    actual_bpm = Column(Integer, nullable=True)
    actual_instruments = Column(Text, nullable=True, comment="实际使用的乐器 JSON")
    actual_prompt_sent = Column(Text, nullable=True, comment="发送给音乐API的完整Prompt")
    provider_name = Column(String(32), nullable=True, comment="skymusic / musicmini / funmusic / local")
    provider_cost_cny = Column(Float, nullable=True, comment="API调用费用(元)")

    # 通用字段
    confidence = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Prescription(id={self.id}, rx_id={self.prescription_id})>"

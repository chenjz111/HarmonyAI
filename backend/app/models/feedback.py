"""Feedback model — stores Agent ⑤ (feedback_agent) output.

Maps to agent-schemas.md Agent ⑤ 用户反馈Agent output schema.
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.sql import func

from backend.app.core.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)

    # Agent metadata
    agent_id = Column(String(64), default="feedback_agent", nullable=False)
    agent_version = Column(String(16), default="1.0.0", nullable=False)
    session_id = Column(String(64), nullable=False, index=True)
    feedback_id = Column(String(64), unique=True, nullable=False, index=True, comment="反馈ID: fb_YYYYMMDD_NNN")

    # Subjective ratings (Likert 1-5)
    subjective_satisfaction = Column(Integer, nullable=True, comment="整体满意度 1-5")
    subjective_emotion_match = Column(Integer, nullable=True, comment="情绪匹配度 1-5")
    subjective_relaxation = Column(Integer, nullable=True, comment="放松感 1-5")
    subjective_sleep = Column(Integer, nullable=True, comment="睡眠改善 1-5")
    subjective_stress = Column(Integer, nullable=True, comment="压力减轻 1-5")
    subjective_text = Column(Text, nullable=True, comment="文字反馈")

    # Behavioral data
    behavioral_completion_rate = Column(Float, nullable=True, comment="完成率 0-1")
    behavioral_replay_count = Column(Integer, nullable=True, comment="重播次数")
    behavioral_pause_count = Column(Integer, nullable=True, comment="暂停次数")
    behavioral_skip_count = Column(Integer, nullable=True, comment="快进次数")
    behavioral_listen_session = Column(String(16), nullable=True, comment="收听时段")
    behavioral_avg_volume = Column(Float, nullable=True, comment="平均音量 0-1")

    # Wearable data (reserved for future)
    wearable_data = Column(Text, nullable=True, comment="可穿戴设备数据 JSON (heart_rate/hrv/sleep/respiration)")

    # Decision
    decision_action = Column(String(16), nullable=False, comment="决策: continue/adjust/rediag")
    decision_detail = Column(Text, nullable=True)
    decision_next_step = Column(String(64), nullable=True)
    decision_adjustments = Column(Text, nullable=True, comment="调整参数 JSON")

    # User profile update (learned from feedback)
    profile_update = Column(Text, nullable=True, comment="用户画像更新 JSON")

    # 通用字段
    confidence = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Feedback(id={self.id}, action={self.decision_action}, satisfaction={self.subjective_satisfaction})>"

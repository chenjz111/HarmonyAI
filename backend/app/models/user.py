"""User model — stores user account and profile information."""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from backend.app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(128), unique=True, nullable=False, index=True, comment="微信OpenID")
    nickname = Column(String(64), nullable=True, comment="用户昵称")
    avatar_url = Column(Text, nullable=True, comment="头像URL")
    phone = Column(String(20), nullable=True, comment="手机号")

    # User profile learned from feedback loop (Agent ⑤ → user_profile_update)
    preferred_instruments = Column(Text, nullable=True, comment="偏好的乐器 JSON")
    preferred_bpm_min = Column(Integer, nullable=True, comment="偏好BPM下限")
    preferred_bpm_max = Column(Integer, nullable=True, comment="偏好BPM上限")
    preferred_session = Column(String(32), nullable=True, comment="偏好时段 bedtime/morning/afternoon")
    effective_syndrome_data = Column(Text, nullable=True, comment="有效证型处方映射 JSON")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, nickname={self.nickname})>"

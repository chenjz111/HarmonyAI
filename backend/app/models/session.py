"""Session model — tracks user conversation sessions."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from backend.app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="FK→users.id",
    )
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment="会话ID: sess_YYYYMMDD_NNN")
    status = Column(String(16), default="active", comment="active / completed / abandoned")
    current_agent = Column(String(32), nullable=True, comment="当前所在Agent: evaluation/diagnosis/prescription/generation/feedback")
    metadata_json = Column(Text, nullable=True, comment="会话元数据 JSON")
    flow_version = Column(
        String(16), nullable=True, comment="V3 writes v3; V2 rows may be null"
    )

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Session(session_id={self.session_id}, status={self.status})>"

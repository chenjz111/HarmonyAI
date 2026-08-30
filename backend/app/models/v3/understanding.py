"""Immutable Understanding snapshot persistence (Amendment 001 §4.2)."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class V3UnderstandingSnapshot(Base):
    __tablename__ = "v3_understanding_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "understanding_id",
            "revision",
            name="uq_v3_understanding_revision",
        ),
        CheckConstraint("revision >= 1", name="ck_v3_understanding_revision"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    understanding_id = Column(String(64), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    session_id = Column(
        String(64),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(32), nullable=False)
    snapshot_json = Column(Text, nullable=False)
    safety_policy = Column(String(32), nullable=True)
    safety_evaluation_status = Column(String(32), nullable=True)
    safety_status = Column(String(32), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

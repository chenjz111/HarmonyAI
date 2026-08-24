"""V3 session-supporting persistence models."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class V3IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "internal_user_pk",
            "operation",
            "idempotency_key",
            name="uq_idempotency_owner_operation",
        ),
        CheckConstraint(
            "status IN ('processing', 'succeeded', 'failed')",
            name="ck_idempotency_status",
        ),
    )

    idempotency_record_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_hash = Column(String(96), nullable=False)
    resource_type = Column(String(32), nullable=True)
    resource_id = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False)
    response_code = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

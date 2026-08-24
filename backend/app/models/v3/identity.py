"""V3 public identity mapping and profile persistence."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from backend.app.core.database import Base


class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (
        CheckConstraint(
            "auth_type IN ('registered', 'guest')",
            name="ck_user_identities_auth_type",
        ),
        CheckConstraint(
            "(auth_type = 'guest' AND guest_expires_at IS NOT NULL) OR "
            "(auth_type = 'registered' AND guest_expires_at IS NULL)",
            name="ck_user_identities_guest_expiry",
        ),
    )

    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    public_user_id = Column(String(64), unique=True, nullable=False, index=True)
    auth_type = Column(String(16), nullable=False)
    guest_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    nickname = Column(String(64), nullable=True)
    avatar_storage_key = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

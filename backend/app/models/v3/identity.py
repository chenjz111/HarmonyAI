"""V3 public identity mapping and profile persistence."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import VARCHAR

from backend.app.core.database import Base


class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (
        CheckConstraint('auth_epoch >= 0', name='ck_user_identities_auth_epoch'),
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
    auth_epoch = Column(Integer, nullable=False, server_default='0')
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


class AuthSession(Base):
    """Persistence only; no issuer, refresh flow, credential algorithm or TTL."""
    __tablename__ = 'auth_sessions'
    __table_args__ = (
        UniqueConstraint('refresh_credential_hash', name='uq_auth_sessions_refresh_hash'),
        CheckConstraint('expires_at > created_at', name='ck_auth_sessions_expiry'),
        CheckConstraint('revoked_at IS NULL OR revoked_at >= created_at', name='ck_auth_sessions_revocation'),
        CheckConstraint('length(refresh_credential_hash) > 0', name='ck_auth_sessions_hash_nonempty'),
        Index('ix_auth_sessions_owner', 'internal_user_pk'),
        Index('ix_auth_sessions_family', 'family_id'),
        Index('ix_auth_sessions_expiry', 'expires_at'),
    )
    auth_session_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    refresh_credential_hash = Column(
        String(255).with_variant(VARCHAR(255, charset='utf8mb4', collation='utf8mb4_bin'), 'mysql'),
        nullable=False,
    )
    family_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

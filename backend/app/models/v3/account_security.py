"""Additive R1 account evidence; reuse existing identity and AuthSession authority."""
from sqlalchemy import Column,String,Integer,DateTime,ForeignKey,CheckConstraint,Index
from sqlalchemy.dialects.mysql import VARCHAR,DATETIME
from backend.app.core.database import Base


def text_type(length):return String(length).with_variant(VARCHAR(length,charset='ascii',collation='ascii_bin'),'mysql')
def timestamp():return DateTime(timezone=True).with_variant(DATETIME(fsp=6),'mysql')


class AccountCredential(Base):
    __tablename__='account_credentials'
    __table_args__=(CheckConstraint('length(username) BETWEEN 3 AND 32',name='ck_account_username_length'),
        CheckConstraint("username = lower(username) AND username NOT GLOB '*[^a-z0-9_]*'",name='ck_account_username_sqlite').ddl_if(dialect='sqlite'),
        CheckConstraint("username = lower(username) AND username REGEXP '^[a-z0-9_]{3,32}$'",name='ck_account_username_mysql').ddl_if(dialect='mysql'),{'mysql_engine':'InnoDB'})
    internal_user_pk=Column(Integer,ForeignKey('user_identities.internal_user_pk',ondelete='RESTRICT'),primary_key=True)
    username=Column(text_type(32),nullable=False,unique=True)
    password_hash=Column(text_type(255),nullable=False)
    created_at=Column(timestamp(),nullable=False)
    updated_at=Column(timestamp(),nullable=False)


class RegisteredSessionState(Base):
    __tablename__='registered_session_state'
    __table_args__=(CheckConstraint('absolute_expires_at > created_at',name='ck_registered_absolute_expiry'),
        CheckConstraint("platform IN ('android','h5')",name='ck_registered_platform'),{'mysql_engine':'InnoDB'})
    auth_session_id=Column(String(64),ForeignKey('auth_sessions.auth_session_id',ondelete='RESTRICT'),primary_key=True)
    absolute_expires_at=Column(timestamp(),nullable=False)
    csrf_hash=Column(text_type(71),nullable=False)
    platform=Column(String(8),nullable=False)
    created_at=Column(timestamp(),nullable=False)


class RefreshProof(Base):
    __tablename__='auth_refresh_proofs'
    __table_args__=(CheckConstraint('expires_at > issued_at',name='ck_refresh_expiry'),
        CheckConstraint('consumed_at IS NULL OR consumed_at >= issued_at',name='ck_refresh_consumed'),
        Index('ix_refresh_proofs_session','auth_session_id'),{'mysql_engine':'InnoDB'})
    credential_hash=Column(text_type(71),primary_key=True)
    auth_session_id=Column(String(64),ForeignKey('auth_sessions.auth_session_id',ondelete='RESTRICT'),nullable=False)
    issued_at=Column(timestamp(),nullable=False)
    expires_at=Column(timestamp(),nullable=False)
    consumed_at=Column(timestamp(),nullable=True)


class LoginBucket(Base):
    __tablename__='account_login_buckets'
    __table_args__=(CheckConstraint("kind IN ('account','source')",name='ck_login_bucket_kind'),
        CheckConstraint('attempts >= 0 AND failures >= 0',name='ck_login_bucket_counts'),{'mysql_engine':'InnoDB'})
    bucket_key=Column(text_type(71),primary_key=True)
    kind=Column(String(8),nullable=False)
    window_started_at=Column(timestamp(),nullable=False)
    attempts=Column(Integer,nullable=False)
    failures=Column(Integer,nullable=False)
    next_allowed_at=Column(timestamp(),nullable=True)

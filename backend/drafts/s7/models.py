"""Unregistered INT-2 models on a separate metadata graph.

Copy existing table definitions to resolve FKs without mutating production
metadata. Importing this module does not connect or execute DDL. Feedback and
preference extensions deliberately exist only in the SQL drafts/field contract.
"""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, MetaData, String,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

import backend.app.models  # noqa: F401 -- completes existing FK definitions
from backend.app.core.database import Base

draft_metadata = MetaData()
for table in Base.metadata.tables.values():
    table.to_metadata(draft_metadata)
DraftBase = declarative_base(metadata=draft_metadata)

# Required parent key for owner+asset+task context integrity. Draft copy only.
Index('uq_s7_task_context_ref',
      draft_metadata.tables['generation_tasks'].c.task_id,
      draft_metadata.tables['generation_tasks'].c.internal_user_pk,
      draft_metadata.tables['generation_tasks'].c.music_asset_id, unique=True)


class OwnerMusicState(DraftBase):
    __tablename__ = 'owner_music_state'
    __table_args__ = (
        CheckConstraint('library_epoch >= 0', name='ck_oms_library_epoch'),
        CheckConstraint('feedback_evidence_epoch >= 0', name='ck_oms_feedback_epoch'),
    )
    internal_user_pk = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    library_epoch = Column(BigInteger, nullable=False, server_default='0')
    feedback_evidence_epoch = Column(BigInteger, nullable=False, server_default='0')
    preference_clear_cutoff = Column(DateTime(timezone=True), nullable=True)


class MusicLibraryState(DraftBase):
    __tablename__ = 'music_library_state'
    __table_args__ = (
        CheckConstraint('metadata_version >= 0', name='ck_mls_metadata_version'),
        Index('ix_mls_owner_played', 'internal_user_pk', 'last_played_at', 'music_asset_id'),
    )
    internal_user_pk = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    music_asset_id = Column(String(64), ForeignKey('music_assets.music_asset_id'), primary_key=True)
    user_title = Column(String(255), nullable=True)
    last_played_at = Column(DateTime(timezone=True), nullable=True)
    metadata_version = Column(BigInteger, nullable=False, server_default='0')


class MusicPlaybackEvent(DraftBase):
    __tablename__ = 'music_playback_events'
    __table_args__ = (
        CheckConstraint("event_type = 'play_started'", name='ck_mpe_event_type'),
        CheckConstraint("length(event_id) BETWEEN 1 AND 128", name='ck_mpe_event_id'),
        ForeignKeyConstraint(
            ['origin_task_id', 'internal_user_pk', 'music_asset_id'],
            ['generation_tasks.task_id', 'generation_tasks.internal_user_pk', 'generation_tasks.music_asset_id'],
            name='fk_mpe_owner_asset_context'),
        Index('ix_mpe_owner_asset_played', 'internal_user_pk', 'music_asset_id', 'played_at'),
    )
    internal_user_pk = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    event_id = Column(String(128), primary_key=True)
    music_asset_id = Column(String(64), ForeignKey('music_assets.music_asset_id'), nullable=False)
    origin_task_id = Column(String(64), nullable=True)
    event_type = Column(String(16), nullable=False, server_default='play_started')
    played_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

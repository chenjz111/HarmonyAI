"""Sprint 7 Backend music-library persistence models.

This module is the **model contract** for migration ``0012_v3_music_library``.
Integration (Issue #150) owns the paired SQLite/MySQL DDL, the shared
``models/v3/__init__.py`` exports and the ``main.py`` wiring; this file is only
the Backend side of that contract and deliberately contains no DDL, no
migration number and no import from any shared module.

Boundary rules this contract encodes (docs/sprint7/S7_W2_IMPLEMENTATION_BOUNDARY.md):

- ``music_library_state`` is the private per-owner title sidecar.  Writing a
  private title must never modify ``music_assets.title`` or its checksum, so the
  sidecar is keyed by ``(owner, asset)`` and carries its own
  ``metadata_version`` for compare-and-swap.
- ``music_playback_events`` stores *real playback* only.  ``event_id`` is unique
  per owner (an idempotency key, not a global one), ``occurred_at`` is always
  assigned by the server, and ``music_assets``/``favorites`` rows grant nothing
  on their own.
- ``owner_music_state`` is the single Backend-owned owner state row that carries
  the pagination ``library_epoch`` and the Preference
  ``feedback_evidence_epoch``.  Preference must not build a second owner-state
  table; the row is created lazily by an explicit write and never by a GET.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    ForeignKeyConstraint,
    column,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class MusicLibraryState(Base):
    """Private per-owner library sidecar (title alias + metadata version)."""

    __tablename__ = "music_library_state"
    __table_args__ = (
        CheckConstraint(
            "metadata_version >= 0", name="ck_music_library_state_version"
        ),
        CheckConstraint(
            column('user_title').is_(None) | ((func.char_length(column('user_title')) >= 1) & (func.char_length(column('user_title')) <= 120)),
            name="ck_music_library_state_title",
        ),
    )

    owner_internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    music_asset_id = Column(
        String(64),
        ForeignKey("music_assets.music_asset_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_title = Column(String(120), nullable=True)
    metadata_version = Column(BigInteger, nullable=False, default=0, server_default='0')
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MusicPlaybackEvent(Base):
    """A real ``play_started`` event.  Page views, prefetch and seek are not plays."""

    __tablename__ = "music_playback_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ['source_context_id','internal_user_pk','music_asset_id'],
            ['generation_tasks.task_id','generation_tasks.internal_user_pk','generation_tasks.music_asset_id'],
            name='fk_playback_owner_asset_context',
        ),
        UniqueConstraint(
            "internal_user_pk", "event_id", name="uq_music_playback_events_owner_event"
        ),
        CheckConstraint(
            "event_type IN ('play_started')", name="ck_music_playback_events_type"
        ),
        CheckConstraint(
            "length(event_id) >= 1 AND length(event_id) <= 64",
            name="ck_music_playback_events_event_id",
        ),
        CheckConstraint(
            "source_context_id IS NULL OR length(source_context_id) <= 64",
            name="ck_music_playback_events_context",
        ),
        {'sqlite_autoincrement': True},
    )

    playback_event_row_id = Column(Integer, primary_key=True, autoincrement=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(String(64), nullable=False)
    music_asset_id = Column(
        String(64),
        ForeignKey("music_assets.music_asset_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(24), nullable=False)
    # Explicit, owner-verified generation context.  NULL means "no context was
    # selected"; it is never filled in from whichever session happens to be live.
    source_context_id = Column(String(64), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OwnerMusicState(Base):
    """Single Backend-owned owner state row (pagination + feedback epochs)."""

    __tablename__ = "owner_music_state"
    __table_args__ = (
        CheckConstraint("library_epoch >= 0", name="ck_owner_music_state_library_epoch"),
        CheckConstraint(
            "feedback_evidence_epoch >= 0", name="ck_owner_music_state_feedback_epoch"
        ),
    )

    owner_internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    library_epoch = Column(BigInteger, nullable=False, default=0, server_default='0')
    feedback_evidence_epoch = Column(BigInteger, nullable=False, default=0, server_default='0')
    preference_clear_cutoff = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

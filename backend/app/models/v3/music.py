"""V3 music generation / asset persistence models.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 7. The circular
FK between music_assets and generation_tasks is handled by
SQLAlchemy's create_all dependency sorting.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class MusicAsset(Base):
    __tablename__ = "music_assets"
    __table_args__ = (
        UniqueConstraint(
            "checksum", "owner_internal_user_pk", name="uq_music_assets_checksum_owner"
        ),
        CheckConstraint(
            "source_type IN ('generated', 'matched', 'comfort_audio')",
            name="ck_music_assets_source_type",
        ),
        CheckConstraint(
            "format IN ('mp3', 'wav', 'm4a')", name="ck_music_assets_format"
        ),
        CheckConstraint(
            "duration_seconds > 0", name="ck_music_assets_duration"
        ),
        CheckConstraint(
            "checksum LIKE 'sha256:%'", name="ck_music_assets_checksum"
        ),
        CheckConstraint(
            "bpm IS NULL OR (bpm >= 40 AND bpm <= 120)", name="ck_music_assets_bpm"
        ),
        CheckConstraint(
            "playable_status IN ('ready', 'expired', 'quarantined', 'deleted')",
            name="ck_music_assets_playable",
        ),
        CheckConstraint(
            "(source_type = 'generated' AND generation_task_id IS NOT NULL) OR "
            "(source_type != 'generated')",
            name="ck_music_assets_generated_source",
        ),
    )

    music_asset_id = Column(String(64), primary_key=True)
    owner_internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    generation_task_id = Column(
        String(64),
        ForeignKey("generation_tasks.task_id", use_alter=True, name="fk_music_assets_generation_task"),
        nullable=True,
    )
    source_type = Column(String(16), nullable=False)
    catalog_track_id = Column(String(64), nullable=True)
    title = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=False)
    format = Column(String(8), nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    checksum = Column(String(96), nullable=False)
    tone_profile_json = Column(JSON, nullable=True)
    bpm = Column(Integer, nullable=True)
    instruments_json = Column(JSON, nullable=True)
    playable_status = Column(String(16), nullable=False)
    retention_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        UniqueConstraint(
            "internal_user_pk", "idempotency_key", name="uq_generation_tasks_idem"
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'matched_fallback', "
            "'failed', 'cancelled')",
            name="ck_generation_tasks_status",
        ),
        CheckConstraint(
            "progress_value IS NULL OR (progress_value >= 0 AND progress_value <= 100)",
            name="ck_generation_tasks_progress",
        ),
        CheckConstraint(
            "progress_indeterminate IN (0, 1)", name="ck_generation_tasks_indeterminate"
        ),
        CheckConstraint(
            "fallback_applied IN (0, 1)", name="ck_generation_tasks_fallback"
        ),
        CheckConstraint(
            "(status = 'succeeded' AND music_asset_id IS NOT NULL AND fallback_applied = 0) "
            "OR (status = 'matched_fallback' AND music_asset_id IS NOT NULL "
            "AND fallback_applied = 1) "
            "OR (status IN ('queued', 'running', 'failed', 'cancelled') "
            "AND music_asset_id IS NULL)",
            name="ck_generation_tasks_asset_consistency",
        ),
    )

    task_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    prescription_id = Column(
        String(64),
        ForeignKey("prescription_v3.prescription_id"),
        nullable=False,
        index=True,
    )
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(24), nullable=False)
    provider = Column(String(64), nullable=True)
    provider_task_id = Column(String(64), nullable=True)
    progress_value = Column(Integer, nullable=True)
    progress_indeterminate = Column(Integer, nullable=False)
    message_code = Column(String(64), nullable=False)
    fallback_applied = Column(Integer, nullable=False)
    fallback_reason_code = Column(String(64), nullable=True)
    error_code = Column(String(64), nullable=True)
    music_asset_id = Column(
        String(64),
        ForeignKey("music_assets.music_asset_id"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

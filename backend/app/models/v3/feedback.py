"""V3 feedback / preference / favorite persistence models.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 8.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.app.core.database import Base


class FeedbackV3(Base):
    __tablename__ = "feedback_v3"
    __table_args__ = (
        UniqueConstraint("internal_user_pk", "idempotency_key", name="uq_feedback_v3_idem"),
        CheckConstraint(
            "change_label IN ('much_better', 'slightly_better', 'no_change', 'worse')",
            name="ck_feedback_v3_change_label",
        ),
        CheckConstraint(
            "continue_use IS NULL OR continue_use IN ('yes', 'maybe', 'no')",
            name="ck_feedback_v3_continue_use",
        ),
        CheckConstraint(
            "preference_update_status IN ('pending', 'applied', 'failed', 'skipped')",
            name="ck_feedback_v3_preference_status",
        ),
    )

    feedback_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_row_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    music_asset_id = Column(
        String(64),
        ForeignKey("music_assets.music_asset_id"),
        nullable=False,
        index=True,
    )
    change_label = Column(String(16), nullable=False)
    pre_state_snapshot_json = Column(JSON, nullable=True)
    post_state_json = Column(JSON, nullable=True)
    experience_json = Column(JSON, nullable=True)
    continue_use = Column(String(8), nullable=True)
    liked_features_json = Column(JSON, nullable=False)
    adjustment_preferences_json = Column(JSON, nullable=False)
    comment_ciphertext = Column(Text, nullable=True)
    playback_json = Column(JSON, nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    preference_update_status = Column(String(16), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserMusicPreference(Base):
    __tablename__ = "user_music_preferences"
    __table_args__ = (
        UniqueConstraint("internal_user_pk", name="uq_user_music_preferences_user"),
    )

    profile_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_version_id = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserMusicPreferenceVersion(Base):
    __tablename__ = "user_music_preference_versions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "version", name="uq_preference_versions_profile_version"
        ),
        CheckConstraint("version >= 1", name="ck_preference_versions_version"),
        CheckConstraint(
            "preferred_bpm_min IS NULL OR "
            "(preferred_bpm_min >= 40 AND preferred_bpm_min <= 120)",
            name="ck_preference_versions_bpm_min",
        ),
        CheckConstraint(
            "preferred_bpm_max IS NULL OR "
            "(preferred_bpm_max >= 40 AND preferred_bpm_max <= 120)",
            name="ck_preference_versions_bpm_max",
        ),
        CheckConstraint(
            "(preferred_bpm_min IS NULL AND preferred_bpm_max IS NULL) OR "
            "(preferred_bpm_min IS NOT NULL AND preferred_bpm_max IS NOT NULL "
            "AND preferred_bpm_min <= preferred_bpm_max)",
            name="ck_preference_versions_bpm_range",
        ),
        CheckConstraint(
            "bpm_weight IS NULL OR (bpm_weight >= 0 AND bpm_weight <= 1)",
            name="ck_preference_versions_bpm_weight",
        ),
        CheckConstraint(
            "preferred_duration_seconds IS NULL OR preferred_duration_seconds > 0",
            name="ck_preference_versions_duration",
        ),
        CheckConstraint(
            "duration_weight IS NULL OR (duration_weight >= 0 AND duration_weight <= 1)",
            name="ck_preference_versions_duration_weight",
        ),
        CheckConstraint(
            "feedback_count >= 0", name="ck_preference_versions_feedback_count"
        ),
        CheckConstraint(
            "minimum_samples_for_application >= 1",
            name="ck_preference_versions_min_samples",
        ),
    )

    preference_version_id = Column(String(64), primary_key=True)
    profile_id = Column(
        String(64),
        ForeignKey("user_music_preferences.profile_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)
    preferred_bpm_min = Column(Integer, nullable=True)
    preferred_bpm_max = Column(Integer, nullable=True)
    bpm_weight = Column(Float, nullable=True)
    preferred_duration_seconds = Column(Integer, nullable=True)
    duration_weight = Column(Float, nullable=True)
    feedback_count = Column(Integer, nullable=False)
    minimum_samples_for_application = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserPreferenceItem(Base):
    __tablename__ = "user_preference_items"
    __table_args__ = (
        CheckConstraint(
            "category IN ('instrument', 'feature', 'ambient')",
            name="ck_preference_items_category",
        ),
        CheckConstraint(
            "polarity IN ('preferred', 'disliked')",
            name="ck_preference_items_polarity",
        ),
        CheckConstraint(
            "weight >= 0 AND weight <= 1", name="ck_preference_items_weight"
        ),
        CheckConstraint(
            "sample_count >= 0", name="ck_preference_items_sample_count"
        ),
    )

    preference_version_id = Column(
        String(64),
        ForeignKey(
            "user_music_preference_versions.preference_version_id", ondelete="CASCADE"
        ),
        primary_key=True,
    )
    category = Column(String(16), primary_key=True)
    code = Column(String(64), primary_key=True)
    polarity = Column(String(16), primary_key=True)
    weight = Column(Float, nullable=False)
    sample_count = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PreferenceEvent(Base):
    __tablename__ = "preference_events"

    event_id = Column(String(64), primary_key=True)
    profile_id = Column(
        String(64),
        ForeignKey("user_music_preferences.profile_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feedback_id = Column(String(64), nullable=True)
    previous_version_id = Column(String(64), nullable=True)
    new_version_id = Column(String(64), nullable=True)
    patch_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint(
            "internal_user_pk", "music_asset_id", name="uq_favorites_user_asset"
        ),
    )

    favorite_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    music_asset_id = Column(
        String(64),
        ForeignKey("music_assets.music_asset_id"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

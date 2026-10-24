"""V3 feedback / preference / favorite persistence models.

Column/constraint semantics mirror 0002_v3_business migration SQL
and harmonyai-v3-persistence-contract.md section 8.
"""

from sqlalchemy import (
    CheckConstraint,
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql

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
        CheckConstraint("learning_consent IN (0,1) AND ((learning_consent=0 AND consent_policy_version IS NULL AND consented_at IS NULL) OR (learning_consent=1 AND consent_policy_version IS NOT NULL AND length(consent_policy_version) BETWEEN 1 AND 64 AND consented_at IS NOT NULL AND evidence_epoch IS NOT NULL AND source_task_id IS NOT NULL AND playback_event_row_id IS NOT NULL AND request_fingerprint IS NOT NULL))", name='s7_0013_consent'),
        CheckConstraint('evidence_epoch IS NULL OR evidence_epoch>=0', name='s7_0013_epoch'),
        CheckConstraint("typeof(learning_consent)='integer'", name='s7_0013_bool_type').ddl_if(dialect='sqlite'),
        CheckConstraint("evidence_epoch IS NULL OR typeof(evidence_epoch)='integer'", name='s7_0013_epoch_type').ddl_if(dialect='sqlite'),
        CheckConstraint("request_fingerprint IS NULL OR (length(request_fingerprint)=71 AND substr(request_fingerprint,1,7)='sha256:' AND substr(request_fingerprint,8) NOT GLOB '*[^0-9a-f]*')", name='s7_0013_fingerprint').ddl_if(dialect='sqlite'),
        CheckConstraint('playback_event_row_id IS NULL OR source_task_id IS NOT NULL', name='s7_0013_event_context'),
        CheckConstraint("request_fingerprint IS NULL OR (CHAR_LENGTH(request_fingerprint)=71 AND LEFT(request_fingerprint,7)='sha256:' AND SUBSTRING(request_fingerprint,8) REGEXP '^[0-9a-f]+$')", name='s7_0013_mysql_fingerprint').ddl_if(dialect='mysql'),
        ForeignKeyConstraint(['source_task_id', 'internal_user_pk', 'music_asset_id'], ['generation_tasks.task_id', 'generation_tasks.internal_user_pk', 'generation_tasks.music_asset_id'], name='int2_0013_task_fk', ondelete='RESTRICT').ddl_if(dialect='mysql'),
        ForeignKeyConstraint(['playback_event_row_id', 'internal_user_pk', 'music_asset_id', 'source_task_id'], ['music_playback_events.playback_event_row_id', 'music_playback_events.internal_user_pk', 'music_playback_events.music_asset_id', 'music_playback_events.source_context_id'], name='int2_0013_event_fk', ondelete='RESTRICT').ddl_if(dialect='mysql'),
        Index('int2_0013_feedback_owner_deleted', 'internal_user_pk', 'deleted_at', 'created_at', 'feedback_id'),
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
    learning_consent = Column(Integer, nullable=False, server_default='0')
    consent_policy_version = Column(String(64), nullable=True)
    consented_at = Column(DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=True)
    deleted_at = Column(DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=True)
    source_task_id = Column(String(64), ForeignKey('generation_tasks.task_id', ondelete='RESTRICT'), nullable=True)
    playback_event_row_id = Column(Integer, ForeignKey('music_playback_events.playback_event_row_id', ondelete='RESTRICT'), nullable=True)
    evidence_epoch = Column(BigInteger, nullable=True)
    request_fingerprint = Column(String(71).with_variant(mysql.VARCHAR(71, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FeedbackClearReceipt(Base):
    """No expiry/cleanup: temporary Owner-approved R1 engineering policy."""
    __tablename__ = 'feedback_clear_receipts'
    __table_args__ = (
        UniqueConstraint('internal_user_pk', 'operation', 'idempotency_key', name='uq_feedback_clear_owner_operation_key'),
        CheckConstraint("operation='feedback_evidence.clear.v1'", name='ck_feedback_clear_operation'),
        CheckConstraint('resulting_feedback_epoch>0', name='ck_feedback_clear_epoch'),
    )
    operation_id = Column(String(64), primary_key=True)
    internal_user_pk = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    operation = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    request_fingerprint = Column(String(71).with_variant(mysql.VARCHAR(71, charset='ascii', collation='ascii_bin'), 'mysql'), nullable=False)
    cutoff = Column(DateTime(timezone=True).with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=False)
    resulting_feedback_epoch = Column(BigInteger, nullable=False)


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
        CheckConstraint('evidence_epoch IS NULL OR evidence_epoch>=0', name='s7_0013_version_epoch'),
        CheckConstraint("evidence_epoch IS NULL OR typeof(evidence_epoch)='integer'", name='s7_0013_version_epoch_type').ddl_if(dialect='sqlite'),
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
    evidence_epoch = Column(BigInteger, nullable=True)
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

"""Agent 5 feedback and preference-learning service.

Legacy submission persistence is durable and idempotent:
  * Stage 1 (durable, idempotent): persist feedback + favorite linkage and
    commit. This must never be rolled back by a later step.
  * M1 (S7-CHANGE-003): automatic/direct learning and new-generation snapshot
    consumption are disabled. Persisted historical profile reads stay available.

Free-form comments are stored as a non-reversible sha256 hash because no
at-rest encryption key is configured yet; raw comment text never reaches the
datastore or logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Session as SessionModel
from backend.app.models.v3.feedback import (
    Favorite,
    FeedbackV3 as FeedbackRow,
    PreferenceEvent,
    UserMusicPreference,
    UserMusicPreferenceVersion,
    UserPreferenceItem,
)
from backend.app.models.v3.music import MusicAsset
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.feedback import (
    FeedbackPresentation,
    FeedbackV3 as FeedbackV3Request,
    FeedbackV3Output,
    PreferredBpmRange,
    PreferredDuration,
    PreferenceLearning,
    PreferenceUpdate,
    UserPreferenceProfile,
    WeightedPreference,
)
from backend.app.schemas.v3.me import (
    FavoriteItem,
    FavoriteList,
    FavoriteState,
    FeedbackHistory,
    FeedbackHistoryItem,
)
from backend.app.schemas.v3.music import MusicRef
from backend.app.schemas.v3.prescription import (
    PreferenceSnapshot,
    PreferredBpmRange as PrescriptionPreferredBpmRange,
    PreferredDuration as PrescriptionPreferredDuration,
    WeightedPreference as PrescriptionWeightedPreference,
)

_MIN_SAMPLES_FOR_APPLICATION = 3

_FIELD_NAMES = (
    "preferred_instruments",
    "disliked_instruments",
    "preferred_features",
    "disliked_features",
    "preferred_ambient",
    "preferred_bpm_range",
    "preferred_duration_seconds",
)


class OwnedResourceNotFound(RuntimeError):
    pass


class FeedbackConflict(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_comment(comment: str | None) -> str | None:
    if not comment:
        return None
    return f"sha256:{sha256(comment.strip().encode('utf-8')).hexdigest()}"


def _find_owned_asset(db: Session, principal: AuthPrincipal, music_id: str) -> MusicAsset:
    asset = (
        db.query(MusicAsset)
        .filter(
            MusicAsset.music_asset_id == music_id,
            (MusicAsset.owner_internal_user_pk == principal.internal_user_pk)
            | (MusicAsset.owner_internal_user_pk.is_(None)),
        )
        .one_or_none()
    )
    if asset is None:
        raise OwnedResourceNotFound
    return asset


def _is_positive(fb: FeedbackRow) -> bool:
    experience = fb.experience_json or {}
    rating = experience.get("overall_rating")
    if rating is not None:
        return rating >= 4
    return fb.continue_use == "yes"


@dataclass(frozen=True)
class _LearnedItem:
    category: str
    code: str
    polarity: str
    weight: float
    sample_count: int


@dataclass
class _Learned:
    items: list[_LearnedItem] = field(default_factory=list)
    bpm_min: int | None = None
    bpm_max: int | None = None
    bpm_weight: float | None = None
    duration_value: int | None = None
    duration_weight: float | None = None

    def to_snapshot(self) -> dict[str, object]:
        def grouped(category: str, polarity: str) -> list[tuple[str, float, int]]:
            return sorted(
                (item.code, item.weight, item.sample_count)
                for item in self.items
                if item.category == category and item.polarity == polarity
            )

        return {
            "preferred_instruments": grouped("instrument", "preferred"),
            "disliked_instruments": grouped("instrument", "disliked"),
            "preferred_features": grouped("feature", "preferred"),
            "disliked_features": grouped("feature", "disliked"),
            "preferred_ambient": grouped("ambient", "preferred"),
            "preferred_bpm_range": (
                (self.bpm_min, self.bpm_max, self.bpm_weight)
                if self.bpm_min is not None
                else None
            ),
            "preferred_duration_seconds": (
                (self.duration_value, self.duration_weight)
                if self.duration_value is not None
                else None
            ),
        }


def _compute_learned(feedbacks: list[FeedbackRow], assets: dict[str, MusicAsset]) -> _Learned:
    total = len(feedbacks)
    positive = [fb for fb in feedbacks if _is_positive(fb)]
    disliked_sources = [
        fb for fb in feedbacks if "change_instruments" in (fb.adjustment_preferences_json or [])
    ]

    instruments: dict[str, int] = {}
    for fb in positive:
        asset = assets.get(fb.music_asset_id)
        for instrument in (asset.instruments_json if asset else []) or []:
            instruments[instrument] = instruments.get(instrument, 0) + 1
    disliked_instruments: dict[str, int] = {}
    for fb in disliked_sources:
        asset = assets.get(fb.music_asset_id)
        for instrument in (asset.instruments_json if asset else []) or []:
            disliked_instruments[instrument] = (
                disliked_instruments.get(instrument, 0) + 1
            )

    features: dict[str, int] = {}
    for fb in feedbacks:
        for feature in fb.liked_features_json or []:
            features[feature] = features.get(feature, 0) + 1

    learned = _Learned()

    def add_items(counts: dict[str, int], category: str, polarity: str, denominator: int) -> None:
        for code, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
            learned.items.append(
                _LearnedItem(
                    category=category,
                    code=code,
                    polarity=polarity,
                    weight=count / denominator if denominator else 0.0,
                    sample_count=count,
                )
            )

    if positive:
        add_items(instruments, "instrument", "preferred", len(positive))
    if disliked_sources:
        add_items(disliked_instruments, "instrument", "disliked", len(disliked_sources))
    if total:
        add_items(features, "feature", "preferred", total)

    bpms = [
        assets[fb.music_asset_id].bpm
        for fb in positive
        if fb.music_asset_id in assets
        and assets[fb.music_asset_id].bpm is not None
    ]
    if bpms:
        learned.bpm_min = max(40, min(bpms))
        learned.bpm_max = min(120, max(bpms))
        learned.bpm_weight = len(positive) / total

    durations = [
        assets[fb.music_asset_id].duration_seconds
        for fb in positive
        if fb.music_asset_id in assets
        and assets[fb.music_asset_id].duration_seconds is not None
    ]
    if durations:
        learned.duration_value = round(sum(durations) / len(durations))
        learned.duration_weight = len(positive) / total

    return learned


def _current_version(db: Session, profile: UserMusicPreference) -> UserMusicPreferenceVersion | None:
    if profile.current_version_id is None:
        return None
    return (
        db.query(UserMusicPreferenceVersion)
        .filter(
            UserMusicPreferenceVersion.preference_version_id
            == profile.current_version_id
        )
        .one_or_none()
    )


def _current_snapshot(
    db: Session, current: UserMusicPreferenceVersion
) -> dict[str, object]:
    rows = (
        db.query(UserPreferenceItem)
        .filter(
            UserPreferenceItem.preference_version_id
            == current.preference_version_id
        )
        .all()
    )
    learned = _Learned(
        items=[
            _LearnedItem(
                category=row.category,
                code=row.code,
                polarity=row.polarity,
                weight=row.weight,
                sample_count=row.sample_count,
            )
            for row in rows
        ],
        bpm_min=current.preferred_bpm_min,
        bpm_max=current.preferred_bpm_max,
        bpm_weight=current.bpm_weight,
        duration_value=current.preferred_duration_seconds,
        duration_weight=current.duration_weight,
    )
    return learned.to_snapshot()


def _learn_preferences(
    db: Session,
    principal: AuthPrincipal,
    feedback_id: str,
    feedback_count: int,
) -> PreferenceUpdate:
    """M1 safety boundary: no automatic, direct, or recompute learning writes."""
    return PreferenceUpdate(applied=False, previous_version=None,
                            new_version=None, changed_fields=[])


def _replay_output(
    db: Session, principal: AuthPrincipal, fb: FeedbackRow
) -> FeedbackV3Output:
    # Lock the same owner authority used by V3.1 deletion, then force a current
    # locking read; neither a stale identity map nor a pre-lock RR snapshot is
    # evidence that an old idempotency key remains visible.
    from sqlalchemy import select
    from .owner_music_state_service import lock_owner_music_state
    lock_owner_music_state(db, internal_user_pk=principal.internal_user_pk)
    row = db.execute(select(FeedbackRow.__table__.c.deleted_at,
                            FeedbackRow.__table__.c.request_fingerprint).where(
        FeedbackRow.internal_user_pk == principal.internal_user_pk,
        FeedbackRow.feedback_id == fb.feedback_id).with_for_update()).one_or_none()
    if row is None or row.deleted_at is not None or row.request_fingerprint is not None:
        raise FeedbackConflict('legacy replay unavailable for deleted or V3.1 feedback')
    update = PreferenceUpdate(
        applied=False,
        previous_version=None,
        new_version=None,
        changed_fields=[],
    )
    return FeedbackV3Output(
        feedback_id=fb.feedback_id,
        status="saved",
        preference_update=update,
        presentation=FeedbackPresentation(message="反馈已保存。"),
    )


def _change_favorite(db: Session, *, owner_pk: int, music_id: str, desired: bool) -> bool:
    """Apply an actual transition and its epoch in the caller's transaction."""
    from backend.app.services.v3.owner_music_state_service import advance_library_epoch

    query = db.query(Favorite).filter(
        Favorite.internal_user_pk == owner_pk, Favorite.music_asset_id == music_id,
    )
    if desired:
        if query.one_or_none() is not None:
            return False
        db.add(Favorite(favorite_id=f"fav_{uuid.uuid4().hex}",
                        internal_user_pk=owner_pk, music_asset_id=music_id))
        # The unique INSERT must succeed before an epoch can be advanced.
        db.flush()
    else:
        # Count the actual deletion, not a stale ORM read from another writer.
        if query.delete(synchronize_session=False) == 0:
            return False
    advance_library_epoch(db, internal_user_pk=owner_pk)
    return True


def _persist_feedback_stage1(db: Session, fb: FeedbackRow, favorite: bool | None) -> FeedbackRow | None:
    """Commit durable feedback/favorite/epoch together; bounded race recovery.

    Recovery retries only this database transaction, never learning or Providers.
    A conflicting owner-state/favorite insertion must have a committed witness;
    unrelated integrity errors are not treated as successful idempotent replay.
    """
    from backend.app.services.v3.owner_music_state_service import current_owner_music_state

    owner_pk, music_id, key = fb.internal_user_pk, fb.music_asset_id, fb.idempotency_key
    for attempt in range(2):
        db.add(fb)
        try:
            db.flush()
            from .owner_music_state_service import lock_owner_music_state, compare_and_advance_feedback_epoch
            state = lock_owner_music_state(db, internal_user_pk=owner_pk)
            db.refresh(state)
            expected_epoch = int(state.feedback_evidence_epoch)
            if favorite is not None:
                _change_favorite(db, owner_pk=owner_pk, music_id=music_id, desired=favorite)
            compare_and_advance_feedback_epoch(db, internal_user_pk=owner_pk,
                                               expected_epoch=expected_epoch)
            db.commit()
            return None
        except IntegrityError:
            db.rollback()
            replay = db.query(FeedbackRow).filter(
                FeedbackRow.internal_user_pk == owner_pk, FeedbackRow.idempotency_key == key,
            ).one_or_none()
            if replay is not None:
                return replay
            witnessed = (db.query(Favorite).filter(Favorite.internal_user_pk == owner_pk,
                         Favorite.music_asset_id == music_id).one_or_none() is not None
                         or current_owner_music_state(db, internal_user_pk=owner_pk) is not None)
            if attempt or not witnessed:
                raise
        except Exception:
            db.rollback()
            raise
    raise AssertionError('unreachable feedback persistence retry')


def submit_feedback(
    db: Session,
    principal: AuthPrincipal,
    request: FeedbackV3Request,
    idempotency_key: str,
) -> tuple[FeedbackV3Output, bool]:
    session_row = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_id == request.session_id,
            SessionModel.user_id == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if session_row is None:
        raise OwnedResourceNotFound
    asset = _find_owned_asset(db, principal, request.music_ref.music_id)
    if asset.source_type != request.music_ref.source_type:
        raise FeedbackConflict("music_ref source_type does not match stored asset")

    existing = (
        db.query(FeedbackRow)
        .filter(
            FeedbackRow.internal_user_pk == principal.internal_user_pk,
            FeedbackRow.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
        return _replay_output(db, principal, existing), True

    feedback_id = f"fb_{uuid.uuid4().hex}"
    fb = FeedbackRow(
        feedback_id=feedback_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=session_row.id,
        music_asset_id=asset.music_asset_id,
        change_label=request.post_state.change_label,
        pre_state_snapshot_json=request.pre_state_snapshot.model_dump(mode="json"),
        post_state_json=request.post_state.model_dump(mode="json"),
        experience_json=(
            request.experience.model_dump(mode="json")
            if request.experience is not None
            else None
        ),
        continue_use=request.continue_use,
        liked_features_json=request.liked_features,
        adjustment_preferences_json=request.adjustment_preferences,
        comment_ciphertext=_hash_comment(request.comment),
        playback_json=(
            request.playback.model_dump(mode="json")
            if request.playback is not None
            else None
        ),
        idempotency_key=idempotency_key,
        preference_update_status="pending",
    )
    replay = _persist_feedback_stage1(db, fb, request.favorite)
    if replay is not None:
        return _replay_output(db, principal, replay), True

    # S7-CHANGE-003: feedback remains durable; M1 never schedules learning.
    _set_status(db, feedback_id, "skipped")
    db.commit()
    update = PreferenceUpdate(applied=False, previous_version=None,
                              new_version=None, changed_fields=[])
    return (
        FeedbackV3Output(
            feedback_id=feedback_id,
            status="saved",
            preference_update=update,
            presentation=FeedbackPresentation(message="反馈已保存。"),
        ),
        False,
    )


def _set_status(db: Session, feedback_id: str, status: str) -> None:
    fb = (
        db.query(FeedbackRow)
        .filter(FeedbackRow.feedback_id == feedback_id)
        .one()
    )
    if fb.deleted_at is not None:
        raise FeedbackConflict('deleted feedback cannot be processed')
    fb.preference_update_status = status
    db.flush()


def _favorite_refs(db: Session, principal: AuthPrincipal) -> list[MusicRef]:
    rows = (
        db.query(Favorite)
        .filter(Favorite.internal_user_pk == principal.internal_user_pk)
        .all()
    )
    if not rows:
        return []
    assets = {
        asset.music_asset_id: asset
        for asset in db.query(MusicAsset)
        .filter(MusicAsset.music_asset_id.in_([row.music_asset_id for row in rows]))
        .all()
    }
    return [
        MusicRef(music_id=row.music_asset_id, source_type=assets[row.music_asset_id].source_type)
        for row in rows
        if row.music_asset_id in assets
    ]


def list_favorites(db: Session, principal: AuthPrincipal) -> FavoriteList:
    rows = (
        db.query(Favorite)
        .filter(Favorite.internal_user_pk == principal.internal_user_pk)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    assets = {
        asset.music_asset_id: asset
        for asset in db.query(MusicAsset)
        .filter(MusicAsset.music_asset_id.in_([row.music_asset_id for row in rows]))
        .all()
    }
    items = [
        FavoriteItem(
            favorite_id=row.favorite_id,
            music_ref=MusicRef(
                music_id=row.music_asset_id,
                source_type=assets[row.music_asset_id].source_type,
            ),
            favorited_at=_as_utc(row.created_at),
        )
        for row in rows
        if row.music_asset_id in assets
    ]
    return FavoriteList(items=items, total=len(items))


def set_favorite(
    db: Session, principal: AuthPrincipal, music_id: str
) -> FavoriteState:
    asset = _find_owned_asset(db, principal, music_id)
    try:
        if _change_favorite(db, owner_pk=principal.internal_user_pk, music_id=music_id, desired=True):
            db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent successful PUT is an idempotent success, not another bump.
        if db.query(Favorite).filter(Favorite.internal_user_pk == principal.internal_user_pk,
                                    Favorite.music_asset_id == music_id).one_or_none() is None:
            raise
    except Exception:
        db.rollback()
        raise
    return FavoriteState(
        music_ref=MusicRef(music_id=asset.music_asset_id, source_type=asset.source_type),
        is_favorite=True,
    )


def remove_favorite(
    db: Session, principal: AuthPrincipal, music_id: str
) -> FavoriteState:
    asset = _find_owned_asset(db, principal, music_id)
    try:
        if _change_favorite(db, owner_pk=principal.internal_user_pk, music_id=music_id, desired=False):
            db.commit()
    except Exception:
        db.rollback()
        raise
    return FavoriteState(
        music_ref=MusicRef(music_id=asset.music_asset_id, source_type=asset.source_type),
        is_favorite=False,
    )


def list_feedback_history(
    db: Session, principal: AuthPrincipal
) -> FeedbackHistory:
    rows = (
        db.query(FeedbackRow)
        .filter(FeedbackRow.internal_user_pk == principal.internal_user_pk,
                FeedbackRow.deleted_at.is_(None))
        .populate_existing()
        .order_by(FeedbackRow.created_at.desc())
        .all()
    )
    session_ids = {
        row.id: row.session_id
        for row in db.query(SessionModel)
        .filter(SessionModel.id.in_([fb.session_row_id for fb in rows]))
        .all()
    }
    assets = {
        asset.music_asset_id: asset
        for asset in db.query(MusicAsset)
        .filter(MusicAsset.music_asset_id.in_([fb.music_asset_id for fb in rows]))
        .all()
    }
    items = [
        FeedbackHistoryItem(
            feedback_id=fb.feedback_id,
            session_id=session_ids[fb.session_row_id],
            music_ref=MusicRef(
                music_id=fb.music_asset_id,
                source_type=assets[fb.music_asset_id].source_type,
            ),
            change_label=fb.change_label,
            submitted_at=_as_utc(fb.created_at),
        )
        for fb in rows
        if fb.session_row_id in session_ids and fb.music_asset_id in assets
    ]
    return FeedbackHistory(items=items, total=len(items))


def get_preferences(
    db: Session, principal: AuthPrincipal
) -> UserPreferenceProfile:
    profile = (
        db.query(UserMusicPreference)
        .filter(UserMusicPreference.internal_user_pk == principal.internal_user_pk)
        .one_or_none()
    )
    if profile is None or profile.current_version_id is None:
        raise OwnedResourceNotFound
    current = _current_version(db, profile)
    if current is None:
        raise OwnedResourceNotFound
    items = (
        db.query(UserPreferenceItem)
        .filter(
            UserPreferenceItem.preference_version_id == current.preference_version_id
        )
        .all()
    )

    def weighted(category: str, polarity: str) -> list[WeightedPreference]:
        return [
            WeightedPreference(
                code=item.code,
                weight=item.weight,
                sample_count=item.sample_count,
                updated_at=_as_utc(item.created_at),
            )
            for item in items
            if item.category == category and item.polarity == polarity
        ]

    return UserPreferenceProfile(
        schema_version="user_music_preference_v3.0",
        profile_id=profile.profile_id,
        public_user_id=principal.public_user_id,
        version=current.version,
        preferred_instruments=weighted("instrument", "preferred"),
        disliked_instruments=weighted("instrument", "disliked"),
        preferred_features=weighted("feature", "preferred"),
        disliked_features=weighted("feature", "disliked"),
        preferred_ambient=weighted("ambient", "preferred"),
        preferred_bpm_range=(
            PreferredBpmRange(
                min=current.preferred_bpm_min,
                max=current.preferred_bpm_max,
                weight=current.bpm_weight,
            )
            if current.preferred_bpm_min is not None
            else None
        ),
        preferred_duration_seconds=(
            PreferredDuration(
                value=current.preferred_duration_seconds,
                weight=current.duration_weight,
            )
            if current.preferred_duration_seconds is not None
            else None
        ),
        favorite_music_refs=_favorite_refs(db, principal),
        learning=PreferenceLearning(
            feedback_count=current.feedback_count,
            minimum_samples_for_application=current.minimum_samples_for_application,
        ),
    )


def get_latest_preference_snapshot(
    db: Session, principal: AuthPrincipal
) -> PreferenceSnapshot | None:
    """M1 new-generation gateway is disabled; historical get_preferences stays read-only."""
    return None

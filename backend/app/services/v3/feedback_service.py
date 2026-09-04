"""Agent 5 feedback and preference-learning service.

Submission is two-staged:
  * Stage 1 (durable, idempotent): persist feedback + favorite linkage and
    commit. This must never be rolled back by a later step.
  * Stage 2 (best-effort): recompute the immutable preference profile version
    from all feedback. If learning fails, the feedback stays saved and the
    row is marked failed; clients still get a valid FeedbackV3Output with
    preference_update.applied=false.

Free-form comments are stored as a non-reversible sha256 hash because no
at-rest encryption key is configured yet; raw comment text never reaches the
datastore or logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import uuid

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
    if feedback_count < _MIN_SAMPLES_FOR_APPLICATION:
        return PreferenceUpdate(
            applied=False,
            previous_version=None,
            new_version=None,
            changed_fields=[],
        )

    feedbacks = (
        db.query(FeedbackRow)
        .filter(FeedbackRow.internal_user_pk == principal.internal_user_pk)
        .order_by(FeedbackRow.created_at)
        .all()
    )
    asset_ids = {fb.music_asset_id for fb in feedbacks}
    assets = {
        asset.music_asset_id: asset
        for asset in db.query(MusicAsset)
        .filter(MusicAsset.music_asset_id.in_(asset_ids))
        .all()
    }
    learned = _compute_learned(feedbacks, assets)
    learned_snapshot = learned.to_snapshot()

    profile = (
        db.query(UserMusicPreference)
        .filter(UserMusicPreference.internal_user_pk == principal.internal_user_pk)
        .one_or_none()
    )

    if profile is None:
        profile = UserMusicPreference(
            profile_id=f"pref_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
        )
        db.add(profile)
        db.flush()
        new_version = 1
        previous_version = None
        previous_version_id = None
        applied = False
        changed_fields: list[str] = []
    else:
        current = _current_version(db, profile)
        if current is not None and _current_snapshot(db, current) == learned_snapshot:
            return PreferenceUpdate(
                applied=False,
                previous_version=None,
                new_version=None,
                changed_fields=[],
            )
        if current is None:
            new_version = 1
            previous_version = None
            previous_version_id = None
            applied = False
            changed_fields = []
        else:
            previous_snapshot = _current_snapshot(db, current)
            new_version = current.version + 1
            previous_version = current.version
            previous_version_id = current.preference_version_id
            applied = True
            changed_fields = [
                name
                for name in _FIELD_NAMES
                if learned_snapshot.get(name) != previous_snapshot.get(name)
            ]

    version_row = UserMusicPreferenceVersion(
        preference_version_id=f"pver_{uuid.uuid4().hex}",
        profile_id=profile.profile_id,
        version=new_version,
        preferred_bpm_min=learned.bpm_min,
        preferred_bpm_max=learned.bpm_max,
        bpm_weight=learned.bpm_weight,
        preferred_duration_seconds=learned.duration_value,
        duration_weight=learned.duration_weight,
        feedback_count=feedback_count,
        minimum_samples_for_application=_MIN_SAMPLES_FOR_APPLICATION,
    )
    db.add(version_row)
    db.flush()
    for item in learned.items:
        db.add(
            UserPreferenceItem(
                preference_version_id=version_row.preference_version_id,
                category=item.category,
                code=item.code,
                polarity=item.polarity,
                weight=item.weight,
                sample_count=item.sample_count,
            )
        )
    profile.current_version_id = version_row.preference_version_id
    db.add(
        PreferenceEvent(
            event_id=f"evt_{uuid.uuid4().hex}",
            profile_id=profile.profile_id,
            feedback_id=feedback_id,
            previous_version_id=previous_version_id,
            new_version_id=version_row.preference_version_id,
            patch_json={"changed_fields": changed_fields},
        )
    )
    return PreferenceUpdate(
        applied=applied,
        previous_version=previous_version,
        # The frozen validator forbids a non-applied update from claiming a
        # new version (cold start still persists version 1, but the response
        # must not present it as an applied change).
        new_version=new_version if applied else None,
        changed_fields=changed_fields if applied else [],
    )


def _replay_output(
    db: Session, principal: AuthPrincipal, fb: FeedbackRow
) -> FeedbackV3Output:
    update = PreferenceUpdate(
        applied=False,
        previous_version=None,
        new_version=None,
        changed_fields=[],
    )
    if fb.preference_update_status == "applied":
        profile = (
            db.query(UserMusicPreference)
            .filter(UserMusicPreference.internal_user_pk == principal.internal_user_pk)
            .one_or_none()
        )
        current = _current_version(db, profile) if profile is not None else None
        if current is not None and current.version >= 2:
            update = PreferenceUpdate(
                applied=True,
                previous_version=current.version - 1,
                new_version=current.version,
                changed_fields=[],
            )
    return FeedbackV3Output(
        feedback_id=fb.feedback_id,
        status="saved",
        preference_update=update,
        presentation=FeedbackPresentation(message="反馈已保存。"),
    )


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
    db.add(fb)

    # Stage 1 favorite linkage follows the feedback's explicit intent.
    if request.favorite is True:
        favorite = (
            db.query(Favorite)
            .filter(
                Favorite.internal_user_pk == principal.internal_user_pk,
                Favorite.music_asset_id == asset.music_asset_id,
            )
            .one_or_none()
        )
        if favorite is None:
            db.add(
                Favorite(
                    favorite_id=f"fav_{uuid.uuid4().hex}",
                    internal_user_pk=principal.internal_user_pk,
                    music_asset_id=asset.music_asset_id,
                )
            )
    elif request.favorite is False:
        favorite = (
            db.query(Favorite)
            .filter(
                Favorite.internal_user_pk == principal.internal_user_pk,
                Favorite.music_asset_id == asset.music_asset_id,
            )
            .one_or_none()
        )
        if favorite is not None:
            db.delete(favorite)

    db.commit()

    # Stage 2: best-effort preference learning; never rolls back the feedback.
    try:
        feedback_count = (
            db.query(FeedbackRow)
            .filter(FeedbackRow.internal_user_pk == principal.internal_user_pk)
            .count()
        )
        update = _learn_preferences(
            db, principal, feedback_id, feedback_count
        )
        status = "applied" if update.applied else "skipped"
        _set_status(db, feedback_id, status)
        db.commit()
    except Exception:
        db.rollback()
        _set_status(db, feedback_id, "failed")
        db.commit()
        update = PreferenceUpdate(
            applied=False,
            previous_version=None,
            new_version=None,
            changed_fields=[],
        )
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
    favorite = (
        db.query(Favorite)
        .filter(
            Favorite.internal_user_pk == principal.internal_user_pk,
            Favorite.music_asset_id == asset.music_asset_id,
        )
        .one_or_none()
    )
    if favorite is None:
        db.add(
            Favorite(
                favorite_id=f"fav_{uuid.uuid4().hex}",
                internal_user_pk=principal.internal_user_pk,
                music_asset_id=asset.music_asset_id,
            )
        )
        db.commit()
    return FavoriteState(
        music_ref=MusicRef(music_id=asset.music_asset_id, source_type=asset.source_type),
        is_favorite=True,
    )


def remove_favorite(
    db: Session, principal: AuthPrincipal, music_id: str
) -> FavoriteState:
    asset = _find_owned_asset(db, principal, music_id)
    favorite = (
        db.query(Favorite)
        .filter(
            Favorite.internal_user_pk == principal.internal_user_pk,
            Favorite.music_asset_id == asset.music_asset_id,
        )
        .one_or_none()
    )
    if favorite is not None:
        db.delete(favorite)
        db.commit()
    return FavoriteState(
        music_ref=MusicRef(music_id=asset.music_asset_id, source_type=asset.source_type),
        is_favorite=False,
    )


def list_feedback_history(
    db: Session, principal: AuthPrincipal
) -> FeedbackHistory:
    rows = (
        db.query(FeedbackRow)
        .filter(FeedbackRow.internal_user_pk == principal.internal_user_pk)
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
    """Return the latest immutable preference snapshot for Agent3 (prescription).

    Returns None when the user has no applied preference version yet, so the
    prescription service can decide not to apply personalization. This is the
    frozen read interface between Agent5 and Agent3.
    """
    profile = (
        db.query(UserMusicPreference)
        .filter(UserMusicPreference.internal_user_pk == principal.internal_user_pk)
        .one_or_none()
    )
    if profile is None or profile.current_version_id is None:
        return None
    current = _current_version(db, profile)
    if current is None:
        return None
    items = (
        db.query(UserPreferenceItem)
        .filter(
            UserPreferenceItem.preference_version_id == current.preference_version_id
        )
        .all()
    )

    def weighted(category: str, polarity: str) -> list[PrescriptionWeightedPreference]:
        return [
            PrescriptionWeightedPreference(
                code=item.code,
                weight=item.weight,
                sample_count=item.sample_count,
            )
            for item in items
            if item.category == category and item.polarity == polarity
        ]

    return PreferenceSnapshot(
        profile_id=profile.profile_id,
        version=current.version,
        preferred_instruments=weighted("instrument", "preferred"),
        disliked_instruments=weighted("instrument", "disliked"),
        preferred_bpm_range=(
            PrescriptionPreferredBpmRange(
                min=current.preferred_bpm_min,
                max=current.preferred_bpm_max,
                weight=current.bpm_weight,
            )
            if current.preferred_bpm_min is not None
            else None
        ),
        preferred_duration_seconds=(
            PrescriptionPreferredDuration(
                value=current.preferred_duration_seconds,
                weight=current.duration_weight,
            )
            if current.preferred_duration_seconds is not None
            else None
        ),
        preferred_ambient=weighted("ambient", "preferred"),
    )

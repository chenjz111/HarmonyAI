"""PF-1B isolated 0013 service slice; not registered in application routing.

The caller owns the write transaction. No implicit commit, policy decision,
receipt, production migration, or preference learning occurs here.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.services.v3.owner_music_state_service import (
    advance_feedback_epoch,
    feedback_evidence_epoch_for,
    lock_owner_music_state,
)
from backend.drafts.s7_feedback_consent.contracts import (
    EvidenceEpochConflict, FeedbackV31, FeedbackSavedV31, PlaybackProofUnavailable,
    request_fingerprint, replay_decision, resolve_feedback_playback_proof,
    verify_persisted_feedback_content,
)
from backend.drafts.s7_feedback_consent.models import FeedbackCandidate
from backend.app.models.v3.music import MusicAsset


class FeedbackNotFound(LookupError):
    """No feedback belonging to this principal can be disclosed."""


class CandidateConsentNotEnabled(ValueError):
    """True-consent writes await approved policy and production integration."""


def save_unconsented_feedback(
    db: Session, *, principal: AuthPrincipal, request: FeedbackV31,
    idempotency_key: str, now_utc: datetime,
) -> FeedbackSavedV31:
    """Stage a save/replay in the caller transaction; commit must succeed outside.

    Caller starts BEGIN IMMEDIATE on SQLite before any reads. Integrity errors
    propagate so the caller can roll back the entire transaction before retry.
    """
    if type(request) is not FeedbackV31:
        raise TypeError("validated exact FeedbackV31 required")
    if request.learning_consent:
        raise CandidateConsentNotEnabled("candidate true-consent write disabled")
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key.strip()) <= 128:
        raise ValueError("invalid idempotency key")
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError("server timestamp must be timezone-aware UTC")
    key = idempotency_key.strip()
    fingerprint = request_fingerprint(request)
    state = lock_owner_music_state(db, internal_user_pk=principal.internal_user_pk)
    db.refresh(state)
    table = FeedbackCandidate.__table__
    existing = db.execute(select(table).where(
        table.c.internal_user_pk == principal.internal_user_pk,
        table.c.idempotency_key == key,
    )).mappings().one_or_none()
    if existing is not None:
        replay_decision(deleted_at=existing["deleted_at"],
                        stored_fingerprint=existing["request_fingerprint"],
                        incoming_fingerprint=fingerprint, persisted_content=existing, request=request)

    proof = resolve_feedback_playback_proof(db, principal=principal,
        music_id=request.music_ref.music_id, source_context_id=request.source_context_id,
        playback_event_id=request.playback_event_id, session_id=request.session_id)
    source_type = db.scalar(select(MusicAsset.__table__.c.source_type).where(
        MusicAsset.__table__.c.music_asset_id == request.music_ref.music_id))
    if source_type != request.music_ref.source_type:
        raise PlaybackProofUnavailable
    if existing is not None:
        if (existing["session_row_id"] != proof.session_row_id
                or existing["playback_event_row_id"] != proof.playback_event_row_id
                or existing["source_task_id"] != proof.source_context_id):
            raise PlaybackProofUnavailable
        return FeedbackSavedV31(feedback_id=existing["feedback_id"], status="saved",
            current_feedback_epoch=int(state.feedback_evidence_epoch), replayed=True)

    if request.expected_evidence_epoch != state.feedback_evidence_epoch:
        raise EvidenceEpochConflict
    feedback_id = f"fb_{uuid4().hex}"
    db.execute(insert(table).values(
        feedback_id=feedback_id, internal_user_pk=principal.internal_user_pk,
        session_row_id=proof.session_row_id, music_asset_id=request.music_ref.music_id,
        change_label=request.post_state.change_label,
        pre_state_snapshot_json=request.pre_state_snapshot.model_dump(mode="json"),
        post_state_json=request.post_state.model_dump(mode="json"),
        experience_json=request.experience.model_dump(mode="json") if request.experience else None,
        continue_use=request.continue_use, liked_features_json=sorted(request.liked_features),
        adjustment_preferences_json=sorted(request.adjustment_preferences), comment_ciphertext=None,
        playback_json=request.playback.model_dump(mode="json") if request.playback else None,
        idempotency_key=key, preference_update_status="skipped", created_at=now_utc,
        learning_consent=0, consent_policy_version=None, consented_at=None,
        source_task_id=proof.source_context_id, playback_event_row_id=proof.playback_event_row_id,
        evidence_epoch=request.expected_evidence_epoch, request_fingerprint=fingerprint,
    ))
    if request.favorite is not None:
        from .feedback_service import _change_favorite
        _change_favorite(db, owner_pk=principal.internal_user_pk,
                         music_id=request.music_ref.music_id, desired=request.favorite)
    db.flush()
    persisted = db.execute(select(table).where(table.c.feedback_id == feedback_id)).mappings().one()
    verify_persisted_feedback_content(persisted, request)
    epoch = advance_feedback_epoch(db, internal_user_pk=principal.internal_user_pk)
    return FeedbackSavedV31(feedback_id=feedback_id, status="saved",
                            current_feedback_epoch=epoch, replayed=False)


def list_owned_feedback(db: Session, principal: AuthPrincipal) -> list[FeedbackCandidate]:
    """Read-only owner listing; tombstones never appear."""
    from .feedback_v31_candidate_queries import visible_feedback_query
    return list(db.scalars(
        visible_feedback_query(principal).order_by(
            FeedbackCandidate.created_at.desc(), FeedbackCandidate.feedback_id.desc())
    ))


def tombstone_owned_feedback(
    db: Session, *, principal: AuthPrincipal, feedback_id: str,
    expected_epoch: int, now_utc: datetime,
) -> int:
    """Soft-delete once; return current epoch; caller begins/commits transaction."""
    if now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError("tombstone time must be timezone-aware UTC")
    table = FeedbackCandidate.__table__
    owned = (table.c.feedback_id == feedback_id, table.c.internal_user_pk == principal.internal_user_pk)
    row = db.execute(select(table).where(*owned)).mappings().one_or_none()
    if row is None:
        raise FeedbackNotFound("feedback not found")
    state = lock_owner_music_state(db, internal_user_pk=principal.internal_user_pk)
    db.refresh(state)
    row = db.execute(select(table).where(*owned)).mappings().one()
    if row["deleted_at"] is not None:
        return int(state.feedback_evidence_epoch)
    if type(expected_epoch) is not int or expected_epoch < 0 or expected_epoch != state.feedback_evidence_epoch:
        raise EvidenceEpochConflict
    changed = db.execute(update(table).where(*owned, table.c.deleted_at.is_(None)).values(deleted_at=now_utc))
    if changed.rowcount != 1:
        return int(state.feedback_evidence_epoch)
    db.flush()
    return advance_feedback_epoch(db, internal_user_pk=principal.internal_user_pk)

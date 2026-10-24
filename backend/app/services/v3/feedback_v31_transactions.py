"""Commit boundary for internal false-consent saves; no public HTTP contract.

No blind write retry follows an unknown commit. A separate read transaction
may establish the exact persisted feedback witness, never an epoch heuristic.
"""
from sqlalchemy import select

from backend.app.models.v3.feedback import FeedbackV3
from backend.app.models.v3.music import MusicAsset
from backend.app.models.v3.music_library import OwnerMusicState
from . import feedback_v31_service as service, music_library_access
from .feedback_v31_contract import replay_decision


class FeedbackCommitUnknown(RuntimeError):
    """No acknowledged commit or independently verified exact witness."""


def delete_feedback(factory, *, verification_factory, principal, feedback_id, expected_epoch, now_utc):
    from backend.app.schemas.v3.feedback_v31 import EvidenceMutationResult
    with factory() as db:
        if db.get_bind().dialect.name == 'sqlite':
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        try:
            epoch = service.tombstone_owned_feedback(db,principal=principal,feedback_id=feedback_id,
                                                      expected_epoch=expected_epoch,now_utc=now_utc)
        except Exception:
            db.rollback()
            raise
        try:
            db.commit()
            return EvidenceMutationResult(status='deleted',feedback_id=feedback_id,current_feedback_epoch=epoch)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    try:
        with verification_factory() as verification:
            row = verification.execute(select(FeedbackV3.deleted_at,OwnerMusicState.feedback_evidence_epoch)
                .join(OwnerMusicState,OwnerMusicState.owner_internal_user_pk == FeedbackV3.internal_user_pk)
                .where(FeedbackV3.feedback_id == feedback_id,
                       FeedbackV3.internal_user_pk == principal.internal_user_pk)).one_or_none()
            if row is None or row.deleted_at is None:
                raise FeedbackCommitUnknown
            return EvidenceMutationResult(status='deleted',feedback_id=feedback_id,
                                           current_feedback_epoch=int(row.feedback_evidence_epoch))
    except Exception as error:
        raise FeedbackCommitUnknown('delete commit unverified; retry original request') from error


def save_feedback(factory, *, verification_factory, principal, request, idempotency_key, now_utc):
    # A new Session is mandatory: no inherited pending objects/transaction.
    with factory() as db:
        if db.get_bind().dialect.name == 'sqlite':
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        try:
            result = service.save_unconsented_feedback(db, principal=principal, request=request,
                idempotency_key=idempotency_key, now_utc=now_utc)
        except Exception:
            db.rollback()
            raise
        try:
            db.commit()
            return result
        except Exception:
            # The Session is never reused to infer the result of its own commit.
            try:
                db.rollback()
            except Exception:
                pass
    try:
        with verification_factory() as verification:
            table = FeedbackV3.__table__
            row = verification.execute(select(table).where(
                table.c.internal_user_pk == principal.internal_user_pk,
                table.c.idempotency_key == idempotency_key.strip(),
            )).mappings().one_or_none()
            if row is None:
                raise FeedbackCommitUnknown('exact feedback witness unavailable')
            from .feedback_v31_contract import request_fingerprint
            replay_decision(deleted_at=row['deleted_at'], stored_fingerprint=row['request_fingerprint'],
                incoming_fingerprint=request_fingerprint(request), persisted_content=row, request=request)
            proof = music_library_access.resolve_feedback_playback_proof(verification, principal=principal,
                music_id=request.music_ref.music_id, source_context_id=request.source_context_id,
                playback_event_id=request.playback_event_id, session_id=request.session_id)
            source = verification.scalar(select(MusicAsset.source_type).where(MusicAsset.music_asset_id == request.music_ref.music_id))
            if (row['session_row_id'], row['playback_event_row_id'], row['source_task_id'], source) != (
                    proof.session_row_id, proof.playback_event_row_id, proof.source_context_id, request.music_ref.source_type):
                raise FeedbackCommitUnknown('feedback witness proof mismatch')
            epoch = verification.scalar(select(OwnerMusicState.feedback_evidence_epoch).where(
                OwnerMusicState.owner_internal_user_pk == principal.internal_user_pk))
            if epoch is None:
                raise FeedbackCommitUnknown('feedback witness epoch unavailable')
            return result.model_copy(update={'feedback_id':row['feedback_id'],
                                             'replayed':True, 'current_feedback_epoch':int(epoch)})
    except Exception as error:
        raise FeedbackCommitUnknown('commit acknowledgment and exact witness unavailable') from error

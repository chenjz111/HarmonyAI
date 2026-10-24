"""Owner-approved Clear A: revoke future evidence, keep visible history."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4
import json

from sqlalchemy import insert, select
from backend.app.models.v3.feedback import FeedbackClearReceipt
from backend.app.schemas.v3.feedback_v31 import EvidenceMutationRequest, EvidenceClearResult
from .feedback_v31_contract import FeedbackFingerprintConflict, EvidenceEpochConflict
from .feedback_v31_transactions import FeedbackCommitUnknown
from .owner_music_state_service import lock_owner_music_state, compare_and_advance_feedback_epoch, FeedbackEpochConflict

OPERATION = 'feedback_evidence.clear.v1'


def _fingerprint(request):
    if type(request) is not EvidenceMutationRequest:
        raise TypeError('validated exact clear request required')
    payload = json.dumps(request.model_dump(mode='json'), sort_keys=True, separators=(',',':')).encode()
    return 'sha256:'+sha256(OPERATION.encode()+b'\0'+payload).hexdigest()


def _result(row):
    cutoff = row['cutoff']
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return EvidenceClearResult(operation_id=row['operation_id'], cutoff=cutoff,
                               resulting_feedback_epoch=row['resulting_feedback_epoch'])


def _receipt(db, owner, key, *, lock=False):
    table = FeedbackClearReceipt.__table__
    query = select(table).where(table.c.internal_user_pk == owner,
        table.c.operation == OPERATION, table.c.idempotency_key == key)
    return db.execute(query.with_for_update() if lock else query).mappings().one_or_none()


def _insert_receipt(db, values):
    db.execute(insert(FeedbackClearReceipt.__table__).values(**values))


def clear_feedback_evidence(db, *, principal, request, idempotency_key, now_utc):
    fingerprint = _fingerprint(request)
    if not isinstance(idempotency_key,str) or not 1 <= len(idempotency_key.strip()) <= 128:
        raise ValueError('invalid idempotency key')
    if not isinstance(now_utc,datetime) or now_utc.tzinfo is None or now_utc.utcoffset() != timedelta(0):
        raise ValueError('server UTC timestamp required')
    key, owner = idempotency_key.strip(), principal.internal_user_pk
    state = lock_owner_music_state(db, internal_user_pk=owner)
    db.refresh(state, with_for_update=True)
    row = _receipt(db, owner, key, lock=True)
    if row is not None:
        if row['request_fingerprint'] != fingerprint:
            raise FeedbackFingerprintConflict
        return _result(row)
    if state.feedback_evidence_epoch != request.expected_evidence_epoch:
        raise EvidenceEpochConflict
    previous = state.preference_clear_cutoff
    if previous is not None and now_utc < previous.replace(tzinfo=timezone.utc):
        raise EvidenceEpochConflict('clear cutoff cannot go backwards')
    state.preference_clear_cutoff = now_utc
    db.flush()
    try:
        resulting_epoch = compare_and_advance_feedback_epoch(db, internal_user_pk=owner,
            expected_epoch=request.expected_evidence_epoch)
    except FeedbackEpochConflict:
        raise EvidenceEpochConflict from None
    values = dict(operation_id='clear_'+uuid4().hex, internal_user_pk=owner, operation=OPERATION,
        idempotency_key=key, request_fingerprint=fingerprint, cutoff=now_utc,
        resulting_feedback_epoch=resulting_epoch)
    _insert_receipt(db, values)
    db.flush()
    persisted = _receipt(db, owner, key, lock=True)
    db.refresh(state, attribute_names=['preference_clear_cutoff'], with_for_update=True)
    if persisted is None or persisted['cutoff'].replace(tzinfo=timezone.utc) != now_utc or state.preference_clear_cutoff.replace(tzinfo=timezone.utc) != now_utc:
        raise RuntimeError('clear cutoff persistence mismatch')
    return _result(persisted)


def clear_with_commit(factory, *, verification_factory, principal, request, idempotency_key, now_utc):
    with factory() as db:
        if db.get_bind().dialect.name == 'sqlite':
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        try:
            result = clear_feedback_evidence(db, principal=principal, request=request,
                idempotency_key=idempotency_key, now_utc=now_utc)
        except Exception:
            db.rollback()
            raise
        try:
            db.commit()
            return result
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    try:
        with verification_factory() as verification:
            row = _receipt(verification, principal.internal_user_pk, idempotency_key.strip())
            if row is None or row['request_fingerprint'] != _fingerprint(request):
                raise FeedbackCommitUnknown('clear receipt unavailable')
            return _result(row)
    except Exception as error:
        raise FeedbackCommitUnknown('clear commit unverified; retry original key/request') from error

"""Shared V3 idempotency reservation and replay handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.v3.session import V3IdempotencyRecord


class IdempotencyConflict(RuntimeError):
    """The same key was reused for a different request payload."""


class IdempotencyInProgress(RuntimeError):
    """An older request owns the key but has not produced a replay yet."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _find_record(
    db: Session,
    *,
    internal_user_pk: int,
    operation: str,
    idempotency_key: str,
) -> V3IdempotencyRecord | None:
    return (
        db.query(V3IdempotencyRecord)
        .filter(
            V3IdempotencyRecord.internal_user_pk == internal_user_pk,
            V3IdempotencyRecord.operation == operation,
            V3IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )


def _replay_or_raise(
    record: V3IdempotencyRecord,
    *,
    request_hash: str,
) -> tuple[V3IdempotencyRecord, bool]:
    if record.request_hash != request_hash:
        raise IdempotencyConflict
    if record.status == "succeeded" and record.resource_id and record.response_json:
        return record, True
    raise IdempotencyInProgress


def reserve_v3_idempotency(
    db: Session,
    *,
    internal_user_pk: int,
    operation: str,
    idempotency_key: str,
    request_hash: str,
) -> tuple[V3IdempotencyRecord, bool]:
    """Atomically reserve a V3 key, or return its exact completed replay.

    The initial lookup is only an optimization. The unique constraint remains
    authoritative: if two transactions both observe no row, the losing
    transaction rolls back its reservation and reads the winner's committed
    response instead of leaking a database ``IntegrityError``.
    """
    for attempt in range(2):
        record = _find_record(
            db,
            internal_user_pk=internal_user_pk,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if record is not None and _as_utc(record.expires_at) <= _utc_now():
            db.delete(record)
            db.flush()
            record = None
        if record is not None:
            return _replay_or_raise(record, request_hash=request_hash)

        candidate = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=internal_user_pk,
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(candidate)
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()
            winner = _find_record(
                db,
                internal_user_pk=internal_user_pk,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            if winner is None:
                if attempt == 0:
                    continue
                raise error
            return _replay_or_raise(winner, request_hash=request_hash)
        return candidate, False

    raise RuntimeError("idempotency reservation retry exhausted")

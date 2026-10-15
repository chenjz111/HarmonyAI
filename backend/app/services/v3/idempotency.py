"""Shared V3 idempotency reservation and replay handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.v3.session import V3IdempotencyRecord


class IdempotencyConflict(RuntimeError):
    """The same key was reused for a different request payload."""


class IdempotencyInProgress(RuntimeError):
    """An older request owns the key but has not produced a replay yet."""


class IdempotencyFailureReplay(RuntimeError):
    """A previously failed request whose public error is safe to replay."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool,
        next_actions: list[str],
        request_id: str | None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.next_actions = next_actions
        self.request_id = request_id
        super().__init__(f"{code}: {message}")

    @classmethod
    def from_record(cls, record: V3IdempotencyRecord) -> "IdempotencyFailureReplay":
        try:
            payload = json.loads(record.response_json or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            raise IdempotencyInProgress from None
        if not isinstance(payload, dict):
            raise IdempotencyInProgress

        next_actions = payload.get("next_actions", [])
        if not isinstance(next_actions, list) or not all(
            isinstance(item, str) for item in next_actions
        ):
            next_actions = []
        request_id = payload.get("request_id")
        if not isinstance(request_id, str):
            request_id = None
        return cls(
            status_code=int(payload.get("status_code") or record.response_code or 502),
            code=str(payload.get("code") or "V31_PIPELINE_FAILED"),
            message=str(payload.get("message") or "V3.1 AI 链路执行失败。"),
            retryable=bool(payload.get("retryable", False)),
            next_actions=next_actions,
            request_id=request_id,
        )


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
    if record.status == "failed" and record.response_json:
        # A completed failure is still a completed first result.  Keep it for
        # exact replay and for hash-conflict detection; never rerun the
        # provider for the same key and payload.
        return record, True
    if record.status == "failed":
        # Rows written by an older implementation did not persist an error
        # envelope.  Preserve a safe one-time retry for that legacy shape.
        record.status = "processing"
        record.resource_type = None
        record.resource_id = None
        record.response_code = None
        record.response_json = None
        return record, False
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
            result = _replay_or_raise(record, request_hash=request_hash)
            if not result[1] and record.status == "processing":
                # Publish the retry reservation before any business writes so
                # a concurrent identical retry cannot also execute it.
                db.commit()
            return result

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
            result = _replay_or_raise(winner, request_hash=request_hash)
            if not result[1] and winner.status == "processing":
                db.commit()
            return result
        return candidate, False

    raise RuntimeError("idempotency reservation retry exhausted")

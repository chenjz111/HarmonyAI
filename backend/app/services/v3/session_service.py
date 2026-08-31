"""Authenticated V3 session creation, replay, and ownership checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy.orm import Session

from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.session import (
    SessionInputRevision,
    V3IdempotencyRecord,
)
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.session import EntryChoice, EntryReadModel


_OPERATION = "create_v3_session"
FLOW_CONTRACT_V3_OWNER = "v3-owner-flow-1"


class IdempotencyConflict(RuntimeError):
    pass


class OwnedResourceNotFound(RuntimeError):
    pass


class FlowContractUnsupported(RuntimeError):
    def __init__(self, version: str) -> None:
        super().__init__(f"unsupported flow contract version: {version}")
        self.version = version


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _entry_read_model(session_id: str) -> EntryReadModel:
    return EntryReadModel(
        page="entry",
        session_id=session_id,
        title="开始了解你最近的状态",
        description="你可以从近期就诊资料或最近发生的事情开始。",
        choices=[
            EntryChoice(
                id="with_document",
                label="我有近期就诊资料",
                next_route="/v3/material",
            ),
            EntryChoice(
                id="without_document",
                label="我没有近期就诊资料",
                next_route="/v3/narrative",
            ),
        ],
    )


def create_v3_session(
    db: Session,
    principal: AuthPrincipal,
    *,
    idempotency_key: str,
    payload: dict[str, object],
    flow_contract_version: str | None = None,
) -> tuple[EntryReadModel, bool]:
    if (
        flow_contract_version is not None
        and flow_contract_version != FLOW_CONTRACT_V3_OWNER
    ):
        raise FlowContractUnsupported(flow_contract_version)

    request_hash = _request_hash(
        {**payload, "flow_contract_version": flow_contract_version}
    )
    record = db.query(V3IdempotencyRecord).filter(
        V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
        V3IdempotencyRecord.operation == _OPERATION,
        V3IdempotencyRecord.idempotency_key == idempotency_key,
    ).one_or_none()
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded" and record.resource_id:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == record.resource_id,
                SessionModel.user_id == principal.internal_user_pk,
            ).one_or_none()
            if session is not None:
                return _entry_read_model(session.session_id), True

    session_id = f"sess_{uuid.uuid4().hex}"
    if record is None:
        record = V3IdempotencyRecord(
            idempotency_record_id=f"idem_{uuid.uuid4().hex}",
            internal_user_pk=principal.internal_user_pk,
            operation=_OPERATION,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
            expires_at=_utc_now() + timedelta(hours=24),
        )
        db.add(record)
    session = SessionModel(
        user_id=principal.internal_user_pk,
        session_id=session_id,
        status="active",
        current_agent="entry",
        flow_version="v3",
    )
    is_new_flow = flow_contract_version == FLOW_CONTRACT_V3_OWNER
    if is_new_flow:
        session.flow_contract_version = FLOW_CONTRACT_V3_OWNER
        session.safety_policy = "deferred_v3"
        session.input_revision = 1
    db.add(session)
    try:
        db.flush()
        if is_new_flow:
            db.add(
                SessionInputRevision(
                    session_row_id=session.id,
                    input_revision=1,
                    input_mode=None,
                    action="create",
                )
            )
        record.resource_type = "session"
        record.resource_id = session_id
        record.status = "succeeded"
        record.response_code = 201
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _entry_read_model(session_id), False


def get_owned_v3_session(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> EntryReadModel:
    session = db.query(SessionModel).filter(
        SessionModel.session_id == session_id,
        SessionModel.user_id == principal.internal_user_pk,
        SessionModel.flow_version == "v3",
    ).one_or_none()
    if session is None:
        raise OwnedResourceNotFound
    return _entry_read_model(session.session_id)


def get_owned_session_row(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> SessionModel:
    """Return the owned session row (any V3 flow) or raise."""
    session = db.query(SessionModel).filter(
        SessionModel.session_id == session_id,
        SessionModel.user_id == principal.internal_user_pk,
        SessionModel.flow_version == "v3",
    ).one_or_none()
    if session is None:
        raise OwnedResourceNotFound
    return session

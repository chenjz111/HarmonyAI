"""Authenticated V3 session creation, replay, and ownership checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy.orm import Session

from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.activity import V3SessionActivity
from backend.app.models.v3.session import V3IdempotencyRecord
from backend.app.schemas.v3.activity import SUPPORTED_FLOW_CONTRACT_VERSION
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.session import EntryChoice, EntryReadModel


_OPERATION = "create_v3_session"


class IdempotencyConflict(RuntimeError):
    pass


class OwnedResourceNotFound(RuntimeError):
    pass


class FlowContractUnsupported(RuntimeError):
    pass


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
        description="你可以从近期材料或最近发生的事情开始。",
        choices=[
            EntryChoice(
                id="with_document",
                label="我有近期材料",
                next_route="/v3/material",
            ),
            EntryChoice(
                id="without_document",
                label="我没有近期材料",
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
) -> tuple[EntryReadModel, bool]:
    request_hash = _request_hash(payload)
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

    flow_contract_version = payload.get("flow_contract_version")
    if flow_contract_version is not None:
        if flow_contract_version != SUPPORTED_FLOW_CONTRACT_VERSION:
            raise FlowContractUnsupported

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
    db.add(session)
    if flow_contract_version is not None:
        db.add(
            V3SessionActivity(
                session_id=session_id,
                internal_user_pk=principal.internal_user_pk,
                flow_contract_version=SUPPORTED_FLOW_CONTRACT_VERSION,
                input_mode=None,
                input_revision=1,
                active_document_id=None,
                understanding_ref=None,
                questionnaire_ref=None,
            )
        )
    try:
        db.flush()
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

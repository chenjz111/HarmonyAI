"""V3.1 document-set service (Issue #99 step 2).

A DocumentSet snapshots 1-3 ordered active source documents. Creating,
adding, deleting or replacing produces a new revision while keeping the
previous revision for audit. Ownership (same user + session) and ordering are
validated here; the set is bound to the session via an optimistic
input_revision CAS and a session_input_revisions snapshot.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.models.v3.document import DocumentSet, DocumentSetItem
from backend.app.models.v3.session import (
    SessionInputRevision,
    V3IdempotencyRecord,
)
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import DocumentReadModel
from backend.app.services.v3.session_service import (
    FLOW_CONTRACT_V3_OWNER,
    OwnedResourceNotFound,
    get_owned_session_row,
)


_OPERATION = "replace_v3_document_set"
_MIN_DOCUMENTS = 1
_MAX_DOCUMENTS = 3


class FlowContractMismatch(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class InputRevisionConflict(RuntimeError):
    pass


class InvalidDocumentSet(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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


def _owned_document(
    db: Session,
    principal: AuthPrincipal,
    session_row: SessionModel,
    document_id: str,
) -> Document:
    document = (
        db.query(Document)
        .filter(
            Document.document_id == document_id,
            Document.user_id == principal.internal_user_pk,
            Document.session_id == session_row.session_id,
            Document.status != "deleted",
        )
        .one_or_none()
    )
    if document is None:
        raise InvalidDocumentSet(
            "DOCUMENT_NOT_FOUND", "资料不存在或不属于当前会话。"
        )
    return document


def _validate_document_ids(
    db: Session,
    principal: AuthPrincipal,
    session_row: SessionModel,
    document_ids: list[str],
) -> None:
    if not (_MIN_DOCUMENTS <= len(document_ids) <= _MAX_DOCUMENTS):
        raise InvalidDocumentSet("DOCUMENT_SET_SIZE", "需要1到3份资料。")
    if len(set(document_ids)) != len(document_ids):
        raise InvalidDocumentSet("DOCUMENT_SET_DUPLICATE", "资料不能重复。")
    for document_id in document_ids:
        _owned_document(db, principal, session_row, document_id)


def _to_documents(db: Session, set_id: str) -> list[DocumentReadModel]:
    items = (
        db.query(DocumentSetItem)
        .filter(DocumentSetItem.document_set_id == set_id)
        .order_by(DocumentSetItem.position)
        .all()
    )
    documents = []
    for item in items:
        document = db.query(Document).filter(
            Document.document_id == item.document_id
        ).one_or_none()
        if document is None:
            continue
        documents.append(
            DocumentReadModel(
                document_id=document.document_id,
                session_id=document.session_id,
                original_filename=document.original_filename,
                file_type=document.file_type,
                file_size_bytes=document.file_size_bytes,
                status=document.status,
                ocr_confidence=document.ocr_confidence,
                ocr_error_code=document.ocr_error_code,
                ocr_confirmed=document.ocr_confirmed,
            )
        )
    return documents


def _read_model(db: Session, set_row: DocumentSet) -> dict[str, object]:
    return {
        "document_set_id": set_row.document_set_id,
        "revision": set_row.revision,
        "status": set_row.status,
        "documents": [doc.model_dump(mode="json") for doc in _to_documents(db, set_row.document_set_id)],
    }


def _confirmation_from_record(resource_id: str) -> tuple[str | None, int | None]:
    if ":" not in resource_id:
        return None, None
    set_id, input_revision_str = resource_id.split(":", 1)
    try:
        input_revision = int(input_revision_str)
    except ValueError:
        input_revision = None
    return set_id, input_revision


def replace_document_set(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
    document_ids: list[str],
    expected_input_revision: int,
    idempotency_key: str,
) -> tuple[dict[str, object], bool]:
    session_row = get_owned_session_row(db, principal, session_id)
    if session_row.flow_contract_version != FLOW_CONTRACT_V3_OWNER:
        raise FlowContractMismatch

    payload = {"session_id": session_id, "document_ids": document_ids}
    request_hash = _request_hash(payload)
    record = (
        db.query(V3IdempotencyRecord)
        .filter(
            V3IdempotencyRecord.internal_user_pk == principal.internal_user_pk,
            V3IdempotencyRecord.operation == _OPERATION,
            V3IdempotencyRecord.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if record is not None and _as_utc(record.expires_at) <= _utc_now():
        db.delete(record)
        db.flush()
        record = None
    if record is not None:
        if record.request_hash != request_hash:
            raise IdempotencyConflict
        if record.status == "succeeded" and record.resource_id:
            set_id, input_revision = _confirmation_from_record(record.resource_id)
            if set_id is not None:
                set_row = db.query(DocumentSet).filter(
                    DocumentSet.document_set_id == set_id
                ).one_or_none()
                if set_row is not None:
                    result = _read_model(db, set_row)
                    result["input_revision"] = input_revision or session_row.input_revision or 1
                    return result, True

    _validate_document_ids(db, principal, session_row, document_ids)

    previous = (
        db.query(DocumentSet)
        .filter(DocumentSet.session_row_id == session_row.id)
        .order_by(DocumentSet.revision.desc())
        .first()
    )
    new_revision = (previous.revision + 1) if previous else 1
    if previous is not None and previous.status == "active":
        previous.status = "superseded"

    set_id = f"dset_{uuid.uuid4().hex}"
    set_row = DocumentSet(
        document_set_id=set_id,
        internal_user_pk=principal.internal_user_pk,
        session_row_id=session_row.id,
        revision=new_revision,
        status="active",
    )
    db.add(set_row)
    db.flush()
    for position, document_id in enumerate(document_ids, start=1):
        db.add(
            DocumentSetItem(
                document_set_item_id=f"dsetitem_{uuid.uuid4().hex}",
                document_set_id=set_id,
                document_id=document_id,
                position=position,
            )
        )

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

    next_revision = _cas_bind_document_set(
        db, session_row, expected_input_revision, set_id, document_ids[0]
    )
    db.add(
        SessionInputRevision(
            session_row_id=session_row.id,
            input_revision=next_revision,
            input_mode=session_row.input_mode,
            active_document_id=document_ids[0],
            active_understanding_id=session_row.active_understanding_id,
            active_understanding_revision=session_row.active_understanding_revision,
            active_questionnaire_submission_id=session_row.active_questionnaire_submission_id,
            action="replace_document",
        )
    )

    record.resource_type = "document_set"
    record.resource_id = f"{set_id}:{next_revision}"
    record.status = "succeeded"
    record.response_code = 201
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    result = _read_model(db, set_row)
    result["input_revision"] = next_revision
    return result, False


def _cas_bind_document_set(
    db: Session,
    session_row: SessionModel,
    expected: int,
    set_id: str,
    first_document_id: str,
) -> int:
    result = db.execute(
        update(SessionModel)
        .where(
            SessionModel.id == session_row.id,
            SessionModel.input_revision == expected,
        )
        .values(
            input_revision=expected + 1,
            active_document_set_id=set_id,
            active_document_id=first_document_id,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        raise InputRevisionConflict
    return expected + 1


def get_active_document_set(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> dict[str, object]:
    session_row = get_owned_session_row(db, principal, session_id)
    set_row = (
        db.query(DocumentSet)
        .filter(
            DocumentSet.session_row_id == session_row.id,
            DocumentSet.status == "active",
        )
        .order_by(DocumentSet.revision.desc())
        .first()
    )
    if set_row is None:
        raise OwnedResourceNotFound
    result = _read_model(db, set_row)
    result["input_revision"] = session_row.input_revision or 1
    return result

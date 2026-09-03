"""V3 document ownership service (Issue #99).

Unifies V3 session/document ownership: every document is scoped to the
authenticated user, and reads/deletes validate that the document belongs to
the caller (and, for listing, to the requested session).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.session import Session as SessionModel
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import (
    DocumentCreateRequest,
    DocumentList,
    DocumentReadModel,
)


class OwnedResourceNotFound(RuntimeError):
    pass


class SessionNotFound(RuntimeError):
    pass


def _owned_session_row(db: Session, principal: AuthPrincipal, session_id: str) -> SessionModel:
    row = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_id == session_id,
            SessionModel.user_id == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if row is None:
        raise SessionNotFound
    return row


def _to_read_model(document: Document) -> DocumentReadModel:
    return DocumentReadModel(
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


def create_document(
    db: Session,
    principal: AuthPrincipal,
    request: DocumentCreateRequest,
) -> DocumentReadModel:
    _owned_session_row(db, principal, request.session_id)
    document = Document(
        user_id=principal.internal_user_pk,
        session_id=request.session_id,
        document_id=f"doc_{uuid.uuid4().hex}",
        original_filename=request.original_filename,
        file_type=request.file_type,
        file_size_bytes=request.file_size_bytes,
        storage_path=request.storage_path,
        status=request.status,
        ocr_text=request.ocr_text,
        ocr_confidence=request.ocr_confidence,
        ocr_error_code=request.ocr_error_code,
    )
    db.add(document)
    db.commit()
    return _to_read_model(document)


def list_documents(
    db: Session,
    principal: AuthPrincipal,
    session_id: str,
) -> DocumentList:
    _owned_session_row(db, principal, session_id)
    documents = (
        db.query(Document)
        .filter(
            Document.session_id == session_id,
            Document.user_id == principal.internal_user_pk,
            Document.status != "deleted",
        )
        .order_by(Document.created_at)
        .all()
    )
    return DocumentList(
        session_id=session_id,
        documents=[_to_read_model(doc) for doc in documents],
        total=len(documents),
    )


def delete_document(
    db: Session,
    principal: AuthPrincipal,
    document_id: str,
) -> None:
    document = (
        db.query(Document)
        .filter(
            Document.document_id == document_id,
            Document.user_id == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if document is None:
        raise OwnedResourceNotFound
    document.status = "deleted"
    db.commit()

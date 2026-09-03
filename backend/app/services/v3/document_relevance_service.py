"""V3.1 document relevance persistence + read service (Issue #99 step 3).

The relevance assessment is produced by the Information Understanding layer
after OCR. This service persists the outcome (VALID / INVALID / IRRELEVANT /
INSUFFICIENT) per source document, bound to the document set + revision, and
exposes it read-only to the client. INVALID/IRRELEVANT must be excluded from
summary/Agent1/Agent2 downstream; INSUFFICIENT is persisted and returned
explicitly, not silently mapped to success or discard.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from backend.app.models.v3.document import (
    DocumentRelevance,
    DocumentSet,
    DocumentSetItem,
)
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import (
    DocumentRelevanceReadModel,
    DocumentRelevanceRecordRequest,
)


class OwnedResourceNotFound(RuntimeError):
    pass


class InvalidRelevance(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _owned_document_set(
    db: Session,
    principal: AuthPrincipal,
    document_set_id: str,
) -> DocumentSet:
    set_row = (
        db.query(DocumentSet)
        .filter(
            DocumentSet.document_set_id == document_set_id,
            DocumentSet.internal_user_pk == principal.internal_user_pk,
        )
        .one_or_none()
    )
    if set_row is None:
        raise OwnedResourceNotFound
    return set_row


def record_relevance(
    db: Session,
    principal: AuthPrincipal,
    request: DocumentRelevanceRecordRequest,
) -> DocumentRelevanceReadModel:
    set_row = _owned_document_set(db, principal, request.document_set_id)

    item_ids = {
        item.document_id
        for item in db.query(DocumentSetItem)
        .filter(DocumentSetItem.document_set_id == request.document_set_id)
        .all()
    }
    for item in request.items:
        if item.document_id not in item_ids:
            raise InvalidRelevance(
                "RELEVANCE_DOCUMENT_NOT_IN_SET", "该资料不属于该资料集。"
            )

    evaluated_at = _utc_now()
    for item in request.items:
        existing = (
            db.query(DocumentRelevance)
            .filter(
                DocumentRelevance.document_set_id == request.document_set_id,
                DocumentRelevance.document_id == item.document_id,
            )
            .one_or_none()
        )
        if existing is not None:
            db.delete(existing)
        db.add(
            DocumentRelevance(
                document_relevance_id=f"rel_{uuid.uuid4().hex}",
                document_set_id=request.document_set_id,
                document_set_revision=request.document_set_revision,
                document_id=item.document_id,
                outcome=item.outcome,
                reason_codes_json=list(item.reason_codes),
                evaluator=request.evaluator,
                evaluator_version=request.evaluator_version,
                evaluated_at=evaluated_at,
            )
        )
    db.commit()

    set_row = db.query(DocumentSet).filter(
        DocumentSet.document_set_id == request.document_set_id
    ).one()
    return _read_relevance(db, set_row)


def get_relevance(
    db: Session,
    principal: AuthPrincipal,
    document_set_id: str,
) -> DocumentRelevanceReadModel:
    set_row = _owned_document_set(db, principal, document_set_id)
    return _read_relevance(db, set_row)


def _read_relevance(
    db: Session,
    set_row: DocumentSet,
) -> DocumentRelevanceReadModel:
    rows = (
        db.query(DocumentRelevance)
        .filter(DocumentRelevance.document_set_id == set_row.document_set_id)
        .all()
    )
    if not rows:
        raise OwnedResourceNotFound
    revision = rows[0].document_set_revision
    items = [
        {
            "document_id": row.document_id,
            "outcome": row.outcome,
            "reason_codes": list(row.reason_codes_json or []),
            "evaluated_at": (
                row.evaluated_at.isoformat() if row.evaluated_at else ""
            ),
        }
        for row in rows
    ]
    return DocumentRelevanceReadModel(
        document_set_id=set_row.document_set_id,
        document_set_revision=revision,
        items=items,
    )

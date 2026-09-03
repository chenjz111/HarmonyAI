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


_REASON_CODE_WHITELIST = frozenset(
    {
        "OCR_FAILED",
        "EMPTY_CONTENT",
        "NOT_CLINICAL_DOCUMENT",
        "UNRELATED_TOPIC",
        "OUT_OF_WINDOW",
        "LOW_INFORMATION",
    }
)


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

    # Must target the currently-active set and its real revision.
    if set_row.status != "active":
        raise InvalidRelevance(
            "RELEVANCE_SET_NOT_ACTIVE", "该资料集不是当前活动资料集。"
        )
    if request.document_set_revision != set_row.revision:
        raise InvalidRelevance(
            "RELEVANCE_REVISION_MISMATCH", "资料集版本不匹配。"
        )

    item_ids = {
        item.document_id
        for item in db.query(DocumentSetItem)
        .filter(DocumentSetItem.document_set_id == request.document_set_id)
        .all()
    }
    request_ids = {item.document_id for item in request.items}
    # Complete coverage: exactly the set's documents, no missing / no extra.
    if request_ids != item_ids:
        raise InvalidRelevance(
            "RELEVANCE_COVERAGE_INCOMPLETE", "相关性结果未完整覆盖资料集。"
        )
    for item in request.items:
        for code in item.reason_codes:
            if code not in _REASON_CODE_WHITELIST:
                raise InvalidRelevance(
                    "RELEVANCE_REASON_CODE_INVALID", "原因码无效。"
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

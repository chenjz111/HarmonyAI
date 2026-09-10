"""V3.1 document relevance persistence + read service (Issue #110 closeout).

The relevance result is produced by the Information Understanding layer after
OCR. It is a single per-set frozen `DocumentRelevanceResult` (one outcome for
the whole document set). Only VALID may enter summary/Evidence/Agent2 — the
downstream gates are derived from the outcome, never stored. INSUFFICIENT is
persisted and returned explicitly, not mapped to success or discard.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from backend.app.models.v3.document import DocumentRelevance, DocumentSet
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import (
    DocumentRelevanceReadModel,
    DocumentRelevanceRecordRequest,
)
from backend.app.schemas.v3.flow_v31 import DocumentSetRef, RelevanceOutcome


class OwnedResourceNotFound(RuntimeError):
    pass


class InvalidRelevance(RuntimeError):
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
    return _record_relevance_for_set(db, set_row, request)


def _record_relevance_for_set(
    db: Session,
    set_row: DocumentSet,
    request: DocumentRelevanceRecordRequest,
) -> DocumentRelevanceReadModel:

    if set_row.status != "current":
        raise InvalidRelevance(
            "RELEVANCE_SET_NOT_CURRENT", "该资料集不是当前活动资料集。"
        )
    if request.document_set_revision != set_row.revision:
        raise InvalidRelevance(
            "RELEVANCE_REVISION_MISMATCH", "资料集版本不匹配。"
        )

    existing = (
        db.query(DocumentRelevance)
        .filter(
            DocumentRelevance.document_set_id == request.document_set_id,
            DocumentRelevance.revision == request.revision,
        )
        .one_or_none()
    )
    if existing is not None:
        # Relevance revisions are immutable snapshots: never delete-recreate.
        # The (document_set_id, revision) unique constraint also guards against
        # a concurrent duplicate insert.
        raise InvalidRelevance(
            "RELEVANCE_REVISION_EXISTS",
            "该 revision 已存在，请使用新的 revision。",
        )

    row = DocumentRelevance(
        document_relevance_id=f"rel_{uuid.uuid4().hex}",
        document_set_id=request.document_set_id,
        document_set_revision=request.document_set_revision,
        run_id=request.run_id,
        revision=request.revision,
        outcome=request.outcome.value if isinstance(request.outcome, RelevanceOutcome) else request.outcome,
        reason_code=request.reason_code,
        reason=request.reason,
        evaluator=request.evaluator,
        evaluator_version=request.evaluator_version,
        evaluated_at=_utc_now(),
    )
    db.add(row)
    db.commit()

    return _read_model(db, row)


def get_relevance(
    db: Session,
    principal: AuthPrincipal,
    document_set_id: str,
) -> DocumentRelevanceReadModel:
    _owned_document_set(db, principal, document_set_id)
    row = (
        db.query(DocumentRelevance)
        .filter(DocumentRelevance.document_set_id == document_set_id)
        .order_by(DocumentRelevance.revision.desc())
        .first()
    )
    if row is None:
        raise OwnedResourceNotFound
    return _read_model(db, row)


def _read_model(db: Session, row: DocumentRelevance) -> DocumentRelevanceReadModel:
    del db
    outcome = RelevanceOutcome(row.outcome)
    may_continue = outcome is RelevanceOutcome.VALID
    return DocumentRelevanceReadModel(
        schema_version="document_relevance_result_v3.1",
        relevance_result_id=row.document_relevance_id,
        run_id=row.run_id,
        revision=row.revision,
        document_set_ref=DocumentSetRef(
            document_set_id=row.document_set_id,
            revision=row.document_set_revision,
        ),
        outcome=outcome,
        reason_code=row.reason_code,
        reason=row.reason,
        may_enter_summary=may_continue,
        may_form_evidence=may_continue,
        may_enter_agent2=may_continue,
        completed_at=_as_utc(row.evaluated_at),
    )

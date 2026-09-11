"""Authoritative DocumentSet/Relevance gate for V3.1 downstream consumers."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.models import Session as SessionModel
from backend.app.models.v3.document import DocumentRelevance, DocumentSet, DocumentSetItem


class DocumentRelevanceGateError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ActiveDocumentGate:
    document_set_id: str
    document_set_revision: int
    document_ids: tuple[str, ...]
    relevance_result_id: str
    relevance_revision: int


def require_active_document_set_relevance(
    db: Session,
    session_row: SessionModel,
) -> ActiveDocumentGate:
    """Return the ordered active set only when its latest result is VALID."""
    if not session_row.active_document_set_id:
        raise DocumentRelevanceGateError("DOCUMENT_SET_NOT_ACTIVE", "当前没有可用的活动资料集。")
    set_row = (
        db.query(DocumentSet)
        .filter(
            DocumentSet.document_set_id == session_row.active_document_set_id,
            DocumentSet.session_row_id == session_row.id,
            DocumentSet.internal_user_pk == session_row.user_id,
            DocumentSet.status == "current",
        )
        .one_or_none()
    )
    if set_row is None:
        raise DocumentRelevanceGateError("DOCUMENT_SET_NOT_ACTIVE", "当前没有可用的活动资料集。")
    items = (
        db.query(DocumentSetItem)
        .filter(DocumentSetItem.document_set_id == set_row.document_set_id)
        .order_by(DocumentSetItem.position)
        .all()
    )
    document_ids = tuple(item.document_id for item in items)
    if not 1 <= len(document_ids) <= 3 or len(set(document_ids)) != len(document_ids):
        raise DocumentRelevanceGateError("DOCUMENT_SET_NOT_ACTIVE", "当前活动资料集无效。")
    relevance = (
        db.query(DocumentRelevance)
        .filter(
            DocumentRelevance.document_set_id == set_row.document_set_id,
            DocumentRelevance.document_set_revision == set_row.revision,
        )
        .order_by(DocumentRelevance.revision.desc())
        .first()
    )
    if relevance is None:
        raise DocumentRelevanceGateError("DOCUMENT_RELEVANCE_NOT_READY", "资料可用性判断尚未完成。")
    if relevance.outcome == "INSUFFICIENT":
        raise DocumentRelevanceGateError("DOCUMENT_RELEVANCE_INSUFFICIENT", "当前资料不足以进入后续分析。")
    if relevance.outcome in {"INVALID", "IRRELEVANT"}:
        raise DocumentRelevanceGateError("DOCUMENT_RELEVANCE_BLOCKED", "这份资料暂时无法用于本次分析。")
    if relevance.outcome != "VALID":
        raise DocumentRelevanceGateError("DOCUMENT_RELEVANCE_NOT_READY", "资料可用性判断尚未完成。")
    return ActiveDocumentGate(
        document_set_id=set_row.document_set_id,
        document_set_revision=set_row.revision,
        document_ids=document_ids,
        relevance_result_id=relevance.document_relevance_id,
        relevance_revision=relevance.revision,
    )

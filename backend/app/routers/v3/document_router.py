"""V3 document endpoints (Issue #99) — ownership-scoped upload/list/delete."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import (
    DocumentCreateRequest,
    DocumentList,
    DocumentReadModel,
)
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.document_service import (
    OwnedResourceNotFound,
    SessionNotFound,
    create_document,
    delete_document,
    list_documents,
)


router = APIRouter()


@router.post(
    "/documents",
    response_model=V3SuccessEnvelope[DocumentReadModel],
    status_code=201,
)
def create_document_endpoint(
    body: DocumentCreateRequest,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DocumentReadModel]:
    try:
        return v3_success(create_document(db, principal, body))
    except SessionNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应会话。") from None


@router.get(
    "/sessions/{session_id}/documents",
    response_model=V3SuccessEnvelope[DocumentList],
)
def list_documents_endpoint(
    session_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DocumentList]:
    try:
        return v3_success(list_documents(db, principal, session_id))
    except SessionNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应会话。") from None


@router.delete(
    "/documents/{document_id}",
    response_model=V3SuccessEnvelope[dict],
)
def delete_document_endpoint(
    document_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[dict]:
    try:
        delete_document(db, principal, document_id)
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资料。") from None
    return v3_success({"document_id": document_id, "status": "deleted"})

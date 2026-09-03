"""V3.1 document relevance endpoints (Issue #99 step 3)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.routers.v3.transport import V3APIError, v3_success
from backend.app.schemas.v3.common import AuthPrincipal
from backend.app.schemas.v3.document import (
    DocumentRelevanceReadModel,
    DocumentRelevanceRecordRequest,
)
from backend.app.schemas.v3.envelope import V3SuccessEnvelope
from backend.app.services.v3.auth_service import get_current_v3_principal
from backend.app.services.v3.document_relevance_service import (
    InvalidRelevance,
    OwnedResourceNotFound,
    get_relevance,
    record_relevance,
)


router = APIRouter()


@router.post(
    "/document-sets/{document_set_id}/relevance",
    response_model=V3SuccessEnvelope[DocumentRelevanceReadModel],
    status_code=201,
)
def record_relevance_endpoint(
    document_set_id: str,
    body: DocumentRelevanceRecordRequest,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DocumentRelevanceReadModel]:
    try:
        return v3_success(record_relevance(db, principal, body))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资料集。") from None
    except InvalidRelevance as error:
        raise V3APIError(422, error.code, error.message) from None


@router.get(
    "/document-sets/{document_set_id}/relevance",
    response_model=V3SuccessEnvelope[DocumentRelevanceReadModel],
)
def get_relevance_endpoint(
    document_set_id: str,
    principal: AuthPrincipal = Depends(get_current_v3_principal),
    db: Session = Depends(get_db),
) -> V3SuccessEnvelope[DocumentRelevanceReadModel]:
    try:
        return v3_success(get_relevance(db, principal, document_set_id))
    except OwnedResourceNotFound:
        raise V3APIError(404, "RESOURCE_NOT_FOUND", "未找到对应资料集。") from None
